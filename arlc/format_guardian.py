#!/usr/bin/env python3
"""
FORMAT GUARDIAN - Last line of defense before submission.

Validates and fixes answer formats to prevent S_det failures from format issues.
"""

import json
import re
import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from collections import defaultdict


@dataclass
class FormatIssue:
    """Represents a format issue found and fixed."""
    question_id: str
    answer_type: str
    severity: str  # critical, warning, info
    issue: str
    original_value: Any
    fixed_value: Any
    question: str


class FormatGuardian:
    """Validates and fixes answer formats."""

    def __init__(self):
        self.issues: List[FormatIssue] = []

    def fix_boolean(self, value: Any, question_id: str, answer_type: str, question: str) -> Any:
        """Fix boolean format - must be JSON true/false."""
        if value is None:
            return None  # Unanswerable

        if isinstance(value, bool):
            return value  # Already correct

        # Common string representations
        if isinstance(value, str):
            lower_val = value.strip().lower()

            # True values
            if lower_val in ['true', 'yes', 'y', '1']:
                self.issues.append(FormatIssue(
                    question_id=question_id,
                    answer_type=answer_type,
                    severity='critical',
                    issue=f'Boolean as string "{value}" instead of JSON boolean',
                    original_value=value,
                    fixed_value=True,
                    question=question
                ))
                return True

            # False values
            if lower_val in ['false', 'no', 'n', '0']:
                self.issues.append(FormatIssue(
                    question_id=question_id,
                    answer_type=answer_type,
                    severity='critical',
                    issue=f'Boolean as string "{value}" instead of JSON boolean',
                    original_value=value,
                    fixed_value=False,
                    question=question
                ))
                return False

            # Unknown string
            self.issues.append(FormatIssue(
                question_id=question_id,
                answer_type=answer_type,
                severity='critical',
                issue=f'Unparseable boolean string: "{value}"',
                original_value=value,
                fixed_value=None,
                question=question
            ))
            return None

        # Try to convert to bool
        try:
            result = bool(value)
            self.issues.append(FormatIssue(
                question_id=question_id,
                answer_type=answer_type,
                severity='warning',
                issue=f'Non-boolean value {value} converted to {result}',
                original_value=value,
                fixed_value=result,
                question=question
            ))
            return result
        except (ValueError, TypeError, AttributeError):
            return value

    def fix_number(self, value: Any, question_id: str, answer_type: str, question: str) -> Any:
        """Fix number format - must be numeric, no currency symbols."""
        if value is None:
            return None  # Unanswerable

        if isinstance(value, (int, float)):
            return value  # Already correct

        if isinstance(value, str):
            original = value
            # Strip common currency symbols and formatting
            cleaned = value.strip()
            cleaned = re.sub(r'[AED$£€¥USD,\s]', '', cleaned)

            # Try to parse
            try:
                # Check if it's a float or int
                if '.' in cleaned:
                    result = float(cleaned)
                else:
                    result = int(cleaned)

                if cleaned != original:
                    self.issues.append(FormatIssue(
                        question_id=question_id,
                        answer_type=answer_type,
                        severity='critical',
                        issue=f'Number with formatting: "{original}" -> {result}',
                        original_value=original,
                        fixed_value=result,
                        question=question
                    ))

                return result
            except ValueError:
                self.issues.append(FormatIssue(
                    question_id=question_id,
                    answer_type=answer_type,
                    severity='critical',
                    issue=f'Unparseable number: "{value}"',
                    original_value=value,
                    fixed_value=None,
                    question=question
                ))
                return None

        return value

    def fix_date(self, value: Any, question_id: str, answer_type: str, question: str) -> Any:
        """Fix date format - must be YYYY-MM-DD (ISO 8601)."""
        if value is None:
            return None  # Unanswerable

        if isinstance(value, str):
            original = value.strip()

            # Check if already in ISO format
            if re.match(r'^\d{4}-\d{2}-\d{2}$', original):
                return original

            # Try to parse common formats
            date_formats = [
                '%d %B %Y',  # "2 February 2026"
                '%B %d, %Y',  # "February 2, 2026"
                '%d/%m/%Y',  # "02/02/2026"
                '%m/%d/%Y',  # "02/02/2026" (US format)
                '%Y-%m-%d',  # "2026-2-2" (missing zeros)
                '%d-%m-%Y',  # "02-02-2026"
                '%Y/%m/%d',  # "2026/02/02"
                '%d.%m.%Y',  # "02.02.2026"
            ]

            for fmt in date_formats:
                try:
                    dt = datetime.strptime(original, fmt)
                    iso_date = dt.strftime('%Y-%m-%d')

                    self.issues.append(FormatIssue(
                        question_id=question_id,
                        answer_type=answer_type,
                        severity='critical',
                        issue=f'Date in wrong format: "{original}" -> "{iso_date}"',
                        original_value=original,
                        fixed_value=iso_date,
                        question=question
                    ))
                    return iso_date
                except ValueError:
                    continue

            # Try to parse with padding fix (e.g., "2026-2-2" -> "2026-02-02")
            if re.match(r'^\d{4}-\d{1,2}-\d{1,2}$', original):
                parts = original.split('-')
                if len(parts) == 3:
                    year, month, day = parts
                    iso_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"

                    self.issues.append(FormatIssue(
                        question_id=question_id,
                        answer_type=answer_type,
                        severity='critical',
                        issue=f'Date missing zero-padding: "{original}" -> "{iso_date}"',
                        original_value=original,
                        fixed_value=iso_date,
                        question=question
                    ))
                    return iso_date

            # Could not parse
            self.issues.append(FormatIssue(
                question_id=question_id,
                answer_type=answer_type,
                severity='critical',
                issue=f'Unparseable date format: "{value}"',
                original_value=value,
                fixed_value=None,
                question=question
            ))
            return None

        return value

    def fix_name(self, value: Any, question_id: str, answer_type: str, question: str) -> Any:
        """Fix name format - must be clean string, not a sentence."""
        if value is None:
            return None  # Unanswerable

        if not isinstance(value, str):
            # If LLM returned a list for a name question, extract first element
            if isinstance(value, list) and value:
                value = str(value[0])
            else:
                return value

        original = value.strip()
        cleaned = original

        # Check for sentence patterns and extract name
        sentence_patterns = [
            (r'^The defendant is (.+)$', 'defendant'),
            (r'^The case is (.+)$', 'case name'),
            (r'^The claimant is (.+)$', 'claimant'),
            (r'^The respondent is (.+)$', 'respondent'),
            (r'^The judge is (.+)$', 'judge'),
            (r'^The name is (.+)$', 'name'),
        ]

        for pattern, label in sentence_patterns:
            match = re.match(pattern, original, re.IGNORECASE)
            if match:
                cleaned = match.group(1).strip()

                self.issues.append(FormatIssue(
                    question_id=question_id,
                    answer_type=answer_type,
                    severity='critical',
                    issue=f'Name as sentence: "{original}" -> "{cleaned}"',
                    original_value=original,
                    fixed_value=cleaned,
                    question=question
                ))
                break

        # Strip leading articles
        article_pattern = r'^(a|an|the)\s+(.+)$'
        match = re.match(article_pattern, cleaned, re.IGNORECASE)
        if match:
            new_cleaned = match.group(2).strip()

            self.issues.append(FormatIssue(
                question_id=question_id,
                answer_type=answer_type,
                severity='warning',
                issue=f'Name with article: "{cleaned}" -> "{new_cleaned}"',
                original_value=original,
                fixed_value=new_cleaned,
                question=question
            ))
            cleaned = new_cleaned

        # Check if it looks like a sentence (has verb indicators or is very long)
        if len(cleaned) > 100 or re.search(r'\b(is|are|was|were|has|have|had)\b', cleaned):
            self.issues.append(FormatIssue(
                question_id=question_id,
                answer_type=answer_type,
                severity='warning',
                issue=f'Name might be a sentence: "{cleaned}" (length={len(cleaned)})',
                original_value=original,
                fixed_value=cleaned,
                question=question
            ))

        return cleaned

    def fix_names(self, value: Any, question_id: str, answer_type: str, question: str) -> Any:
        """Fix names format - must be JSON array of strings."""
        if value is None:
            return None  # Unanswerable

        if isinstance(value, list):
            # Check if all elements are strings and clean them
            fixed = []
            had_issues = False

            for item in value:
                if isinstance(item, str):
                    # Apply name cleaning to each element
                    cleaned = self.fix_name(item, question_id, 'name', question)
                    fixed.append(cleaned)
                    if cleaned != item:
                        had_issues = True
                else:
                    fixed.append(str(item))
                    had_issues = True

            if had_issues:
                self.issues.append(FormatIssue(
                    question_id=question_id,
                    answer_type=answer_type,
                    severity='warning',
                    issue=f'Names list had formatting issues',
                    original_value=value,
                    fixed_value=fixed,
                    question=question
                ))

            return fixed

        if isinstance(value, str):
            # Try to parse as comma-separated list
            if ',' in value:
                parts = [p.strip() for p in value.split(',')]

                self.issues.append(FormatIssue(
                    question_id=question_id,
                    answer_type=answer_type,
                    severity='critical',
                    issue=f'Names as comma-separated string instead of array',
                    original_value=value,
                    fixed_value=parts,
                    question=question
                ))
                return parts
            else:
                # Single name as string, convert to array
                self.issues.append(FormatIssue(
                    question_id=question_id,
                    answer_type=answer_type,
                    severity='critical',
                    issue=f'Single name as string instead of array',
                    original_value=value,
                    fixed_value=[value],
                    question=question
                ))
                return [value]

        return value

    def fix_free_text(self, value: Any, question_id: str, answer_type: str, question: str) -> Any:
        """Fix free text format - check for emptiness, refusals, and clean formatting."""
        if value is None:
            self.issues.append(FormatIssue(
                question_id=question_id,
                answer_type=answer_type,
                severity='critical',
                issue='Free text answer is null (should be text for unanswerable)',
                original_value=value,
                fixed_value=value,
                question=question
            ))
            return value

        if not isinstance(value, str):
            return value

        original = value
        cleaned = value.strip()

        # Check for emptiness
        if not cleaned:
            self.issues.append(FormatIssue(
                question_id=question_id,
                answer_type=answer_type,
                severity='critical',
                issue='Free text answer is empty or whitespace',
                original_value=original,
                fixed_value=cleaned,
                question=question
            ))
            return cleaned

        # Check for refusal patterns
        refusal_patterns = [
            r"I cannot",
            r"As an AI",
            r"I don't have access",
            r"I apologize",
            r"I'm unable to",
            r"I am unable to",
        ]

        for pattern in refusal_patterns:
            if re.search(pattern, cleaned, re.IGNORECASE):
                self.issues.append(FormatIssue(
                    question_id=question_id,
                    answer_type=answer_type,
                    severity='critical',
                    issue=f'Free text contains refusal pattern: "{pattern}"',
                    original_value=original,
                    fixed_value=cleaned,
                    question=question
                ))
                break

        # Strip markdown formatting (bold, italic, headers)
        if '**' in cleaned or '*' in cleaned or cleaned.startswith('#'):
            md_cleaned = cleaned
            md_cleaned = re.sub(r'\*\*(.+?)\*\*', r'\1', md_cleaned)  # **bold**
            md_cleaned = re.sub(r'\*(.+?)\*', r'\1', md_cleaned)  # *italic*
            md_cleaned = re.sub(r'^#+\s+', '', md_cleaned, flags=re.MULTILINE)  # # headers

            if md_cleaned != cleaned:
                self.issues.append(FormatIssue(
                    question_id=question_id,
                    answer_type=answer_type,
                    severity='info',
                    issue='Stripped markdown formatting from free text',
                    original_value=original,
                    fixed_value=md_cleaned,
                    question=question
                ))
                cleaned = md_cleaned

        # Remove trailing "Caveat:" meta-commentary (agent_v2 adds these)
        caveat_match = re.search(r'\n\n\s*Caveat:\s', cleaned)
        if caveat_match:
            caveat_cleaned = cleaned[:caveat_match.start()].rstrip()
            self.issues.append(FormatIssue(
                question_id=question_id,
                answer_type=answer_type,
                severity='info',
                issue='Removed trailing Caveat meta-commentary',
                original_value=cleaned[caveat_match.start():caveat_match.start() + 80] + '...',
                fixed_value='[removed]',
                question=question
            ))
            cleaned = caveat_cleaned

        return cleaned

    def fix_unanswerable(self, answer: Any, chunk_pages: List, answer_type: str,
                         question_id: str, question: str) -> Tuple[Any, List]:
        """
        Fix unanswerable format.
        - Det types: answer must be JSON null (not string "null", not "N/A")
        - Free text: must be text explaining unavailability, not null
        - chunk_pages: must be [] for unanswerable
        """
        det_types = {'boolean', 'number', 'date', 'name', 'names'}

        # Check if this is unanswerable (null answer or empty pages)
        is_unanswerable = answer is None or not chunk_pages

        if is_unanswerable:
            # Det types: answer should be null
            if answer_type in det_types:
                if isinstance(answer, str) and answer.lower() in ['null', 'n/a', 'none', 'unanswerable']:
                    self.issues.append(FormatIssue(
                        question_id=question_id,
                        answer_type=answer_type,
                        severity='critical',
                        issue=f'Unanswerable det as string "{answer}" instead of JSON null',
                        original_value=answer,
                        fixed_value=None,
                        question=question
                    ))
                    answer = None

            # Free text: should have explanation, not null
            elif answer_type == 'free_text':
                if answer is None:
                    self.issues.append(FormatIssue(
                        question_id=question_id,
                        answer_type=answer_type,
                        severity='warning',
                        issue='Unanswerable free text as null (should have explanation)',
                        original_value=None,
                        fixed_value='The information requested is not available in the provided documents.',
                        question=question
                    ))
                    answer = 'The information requested is not available in the provided documents.'

            # Chunk pages should be empty
            if chunk_pages:
                self.issues.append(FormatIssue(
                    question_id=question_id,
                    answer_type=answer_type,
                    severity='warning',
                    issue=f'Unanswerable question has {len(chunk_pages)} chunk_pages (should be empty)',
                    original_value=len(chunk_pages),
                    fixed_value=0,
                    question=question
                ))
                chunk_pages = []

        return answer, chunk_pages

    def guard_result(self, result: Dict) -> Dict:
        """Validate and fix a single result."""
        question_id = result.get('id', 'unknown')
        answer_type = result.get('answer_type', 'unknown')
        question = result.get('question', '')
        answer = result.get('answer')
        chunk_pages = result.get('chunk_pages', [])

        # Fix based on type
        if answer_type == 'boolean':
            answer = self.fix_boolean(answer, question_id, answer_type, question)
        elif answer_type == 'number':
            answer = self.fix_number(answer, question_id, answer_type, question)
        elif answer_type == 'date':
            answer = self.fix_date(answer, question_id, answer_type, question)
        elif answer_type == 'name':
            answer = self.fix_name(answer, question_id, answer_type, question)
        elif answer_type == 'names':
            answer = self.fix_names(answer, question_id, answer_type, question)
        elif answer_type == 'free_text':
            answer = self.fix_free_text(answer, question_id, answer_type, question)

        # Check unanswerable format
        answer, chunk_pages = self.fix_unanswerable(answer, chunk_pages, answer_type, question_id, question)

        # Update result
        result['answer'] = answer
        result['chunk_pages'] = chunk_pages

        return result

    def guard_results(self, results: List[Dict]) -> List[Dict]:
        """Validate and fix all results."""
        return [self.guard_result(r) for r in results]

    def print_report(self):
        """Print a report of all issues found and fixed."""
        if not self.issues:
            print("\n✅ FORMAT GUARDIAN: All answers passed validation. No issues found.")
            return

        print(f"\n⚠️  FORMAT GUARDIAN: Found {len(self.issues)} format issues\n")

        # Group by severity
        by_severity = defaultdict(list)
        for issue in self.issues:
            by_severity[issue.severity].append(issue)

        # Print critical issues first
        for severity in ['critical', 'warning', 'info']:
            issues = by_severity[severity]
            if not issues:
                continue

            icon = '🔴' if severity == 'critical' else '🟡' if severity == 'warning' else 'ℹ️'
            print(f"{icon} {severity.upper()}: {len(issues)} issues")
            print("-" * 80)

            for issue in issues[:10]:  # Show first 10 of each severity
                print(f"  Type: {issue.answer_type}")
                print(f"  Issue: {issue.issue}")
                print(f"  Question: {issue.question[:100]}...")
                print(f"  Original: {issue.original_value}")
                print(f"  Fixed: {issue.fixed_value}")
                print()

            if len(issues) > 10:
                print(f"  ... and {len(issues) - 10} more {severity} issues\n")

        # Summary by type
        by_type = defaultdict(int)
        for issue in self.issues:
            by_type[issue.answer_type] += 1

        print("\nIssues by answer type:")
        for answer_type, count in sorted(by_type.items(), key=lambda x: -x[1]):
            print(f"  {answer_type}: {count}")

        # Critical issues count
        critical_count = len(by_severity['critical'])
        if critical_count > 0:
            print(f"\n🔴 CRITICAL: {critical_count} issues that would likely cause S_det failures")

        print()


def main():
    parser = argparse.ArgumentParser(
        description='Format Guardian - Validate and fix answer formats before submission'
    )
    parser.add_argument('--results', required=True, help='Path to results JSON file')
    parser.add_argument('--output', required=True, help='Path to output guarded results')
    parser.add_argument('--report', help='Path to save detailed issue report (JSON)')

    args = parser.parse_args()

    # Load results
    results_path = Path(args.results)
    if not results_path.exists():
        print(f"❌ Error: Results file not found: {results_path}")
        return 1

    with open(results_path) as f:
        results = json.load(f)

    print(f"📋 Loaded {len(results)} results from {results_path}")

    # Guard results
    guardian = FormatGuardian()
    guarded_results = guardian.guard_results(results)

    # Save guarded results
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(guarded_results, f, indent=2)

    print(f"💾 Saved guarded results to {output_path}")

    # Print report
    guardian.print_report()

    # Save detailed report if requested
    if args.report:
        report_path = Path(args.report)
        report_data = {
            'total_results': len(results),
            'total_issues': len(guardian.issues),
            'issues': [asdict(issue) for issue in guardian.issues]
        }

        with open(report_path, 'w') as f:
            json.dump(report_data, f, indent=2)

        print(f"📊 Saved detailed report to {report_path}")

    # Return error code if critical issues found
    critical_count = sum(1 for i in guardian.issues if i.severity == 'critical')
    if critical_count > 0:
        return 0  # We fixed them, so not an error

    return 0


if __name__ == '__main__':
    exit(main())
