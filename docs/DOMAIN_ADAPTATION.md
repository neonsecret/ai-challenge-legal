# Domain Adaptation Design: Making ARLC Jurisdiction-Agnostic

## 1. Architecture Overview

```
domains/
  difc.yaml          <-- Domain config: patterns, prompts, metadata schema
  us_federal.yaml
  uk_contracts.yaml

arlc/
  domain.py           <-- DomainConfig loader (singleton, reads YAML at startup)
  plugins/
    __init__.py
    base.py           <-- Abstract DomainPlugin interface
    difc.py           <-- DIFC-specific plugin (complex logic that can't be config-driven)
    us_federal.py
  router.py           <-- Reads patterns from DomainConfig instead of hardcoded regex
  retriever.py        <-- Reads law names, boosts, identifiers from DomainConfig
  answerer.py         <-- Reads prompt templates from DomainConfig
  indexing/
    legal_tokenizer.py  <-- Reads token expansion patterns from DomainConfig
    indexer.py          <-- Reads boilerplate patterns from DomainConfig
  pipeline.py         <-- Reads trick-question config from DomainConfig
  page_verifier.py    <-- No changes needed (already generic)
```

**Data flow:**

```
startup:
  ARLC_DOMAIN=difc python pipeline.py
       |
       v
  domain.py loads domains/difc.yaml --> DomainConfig singleton
       |
       +--> router.py:    Router.__init__() reads config.case_id_patterns, config.law_name_patterns, etc.
       +--> retriever.py: reads config.law_names, config.identifier_patterns, config.hyde_prompt
       +--> answerer.py:  reads config.system_prompts[answer_type], config.trick_keywords
       +--> indexer.py:   reads config.boilerplate_patterns
       +--> tokenizer.py: reads config.token_expansion_patterns
```

## 2. Domain Config File Schema

### 2.1 Full YAML Specification

```yaml
# Domain configuration schema v1.0
# File: domains/<domain_id>.yaml

domain:
  id: "difc"                          # Unique domain identifier
  name: "Dubai International Financial Centre"
  short_name: "DIFC"
  description: "DIFC Courts civil and commercial jurisdiction"

# ---------------------------------------------------------------
# Document type definitions
# ---------------------------------------------------------------
document_types:
  case:
    label: "Court Case"
    id_patterns:
      # Each pattern: regex with named groups <prefix>, <number>, <year>
      - pattern: '(?P<prefix>CFI|SCT|CA|ARB|ENF|DEC|TCD|ACT)[\s\-/]*(?P<number>\d+)\s*(?:/|\-|\s+of\s+)(?P<year>\d{4})'
        flags: IGNORECASE
        # How to normalize the extracted ID for index lookup
        normalize: "{prefix} {number}/{year}"
        # Alternate normalization formats to try if primary misses
        normalize_alts:
          - "{prefix} {number:03d}/{year}"   # zero-padded
          - "{prefix}-{number:03d}-{year}"   # dash format
      - pattern: '(?:DIFC\s+)?(?P<prefix>SCT|CFI|CA|ARB|ENF|DEC|TCD|ACT)\s+(?P<number>\d+)'
        flags: IGNORECASE
        type: "bare"   # no year component
    metadata_fields:
      date_of_issue:
        type: date
        indicators:
          - 'date\s+of\s+issue'
          - 'issue\s+date'
          - 'issued?\s+(?:earlier|later|first|date)'
      claim_value:
        type: number
        indicators:
          - 'claim\s+value'
          - 'monetary\s+claim'
          - '(?:larger|higher|bigger|greater)\s+(?:sum|amount|claim)'
      judge:
        type: name
        default_page: 1
        indicators:
          - '(?:who\s+(?:is|are|was|were)\s+)?(?:the\s+)?judge'
          - 'judge\s+(?:who\s+)?presid'
      parties:
        type: names
        default_page: 1
        indicators:
          - '(?:who\s+(?:is|are)\s+)?(?:the\s+)?(?:claimant|defendant|parties)'
          - '(?:judgment\s+)?(?:creditor|debtor)'
      outcome:
        type: free_text
        indicators:
          - '(?:what\s+was\s+)?(?:the\s+)?(?:result|outcome|ruling|decision)'
          - '(?:court\s+)?(?:decide|rule(?!s\b)|order|grant|dismiss)'
          - 'IT\s+IS\s+HEREBY\s+ORDERED'
    sac_keywords:   # SAC prefix patterns to identify this doc type in index
      - "court case"
  law:
    label: "Law/Regulation"
    sac_keywords:
      - "difc law"
      - "law/enactment"
      - "enactment"
      - "regulation"
  consultation_paper:
    label: "Consultation Paper"
  court_order:
    label: "Court Order"

# ---------------------------------------------------------------
# Law name resolution
# ---------------------------------------------------------------
law_names:
  # Regex patterns to extract law names from questions (ordered by specificity)
  extraction_patterns:
    - '(?:the\s+)?(?:DIFC\s+)?Law\s+on\s+the\s+Application\s+of\s+Civil\s+and\s+Commercial\s+Laws(?:\s+in\s+the\s+DIFC)?'
    - '(?:the\s+)?(?:DIFC\s+)?Common\s+Reporting\s+Standard\s+Law(?:\s+\d{4})?'
    - '(?:the\s+)?(?:DIFC\s+)?Limited\s+Liability\s+Partnership\s+Law(?:\s+\d{4})?'
    - '(?:the\s+)?(?:DIFC\s+)?General\s+Partnership\s+Law(?:\s+\d{4})?'
    - '(?:the\s+)?(?:DIFC\s+)?Personal\s+Property\s+Law(?:\s+\d{4})?'
    - '(?:the\s+)?(?:DIFC\s+)?(Employment|Operating|Foundations|Trust)\s+Law(?:\s+\d{4})?'
    - '(?:the\s+)?(?:DIFC\s+)?([A-Z][a-z]+\s+[A-Z][a-z]+)\s+Law(?:\s+\d{4})?'
    - '(?:the\s+)?(?:DIFC\s+)?([A-Z][a-z]+)\s+Law(?:\s+\d{4})?'

  # Normalization: strip these prefixes before index lookup
  strip_prefixes: ["the ", "difc "]

  # Known abbreviations -> canonical law name
  abbreviations:
    crs: "common reporting standard law"
    gp: "general partnership law"
    llp: "limited liability partnership law"
    pp: "personal property law"
    "ip law": "intellectual property law"

  # Short names (without "Law" suffix) -> index lookup key
  short_names:
    "general partnership": "general partnership"
    "limited liability partnership": "limited liability partnership"
    employment: "employment"
    operating: "operating"
    trust: "trust"
    foundations: "foundations"
    registrar: "operating"   # Registrar = Operating Law entity

  # Law number -> name mapping (jurisdiction-specific numbering)
  number_map:
    "3/2018": "foundations law"
    "4/2004": "general partnership law"
    "1/2019": "employment law"
    "5/2005": "personal property law"
    "7/2018": "operating law"
    "5/2018": "companies law"

  # Pattern for "DIFC Law No. X of YYYY" references
  number_pattern: 'DIFC\s+(?:\w+\s+)?Law\s+No\.?\s*(?P<number>\d+)\s+of\s+(?P<year>\d{4})'

  # Known law names for retriever keyword matching (ordered: amendment laws first)
  known_names:
    - "Employment Law Amendment Law"
    - "General Partnership Law"
    - "Limited Liability Partnership Law"
    - "Employment Law"
    - "Data Protection Law"
    - "Intellectual Property Law"
    - "Real Property Law"
    - "Personal Property Law"
    - "Operating Law"
    - "Common Reporting Standard Law"
    - "Contract Law"
    - "Arbitration Law"
    - "Companies Law"
    - "Insolvency Law"
    - "Trust Law"
    - "Foundations Law"
    - "Court Law"
    - "Companies Regulations"
    - "Employment Regulations"

# ---------------------------------------------------------------
# Legal tokenizer patterns (for BM25 expansion)
# ---------------------------------------------------------------
tokenizer:
  # Each entry: regex pattern with named groups, and expansion template
  patterns:
    - name: "case_id"
      pattern: '\b(?P<prefix>[A-Z]{2,5})[\s\-/](?P<number>\d{2,4})[\s\-/](?P<year>\d{4})\b'
      expansions:
        - "{prefix}_{number}_{year}"   # e.g. "cfi_057_2025"
        - "{number}"
        - "{year}"
    - name: "article_ref"
      pattern: '\b(?:Article|Art\.?)\s+(?P<num>\d+)(?:\((?P<sub1>\w+)\))?(?:\((?P<sub2>\w+)\))?'
      flags: IGNORECASE
      expansions:
        - "article_{num}"
        - "article_{num}_{sub1}"       # only if sub1 captured
        - "article_{num}_{sub1}_{sub2}" # only if sub2 captured
    - name: "law_number"
      pattern: '\b(?P<prefix>\w+)\s+Law\s+No\.?\s*(?P<num>\d+)\s+of\s+(?P<year>\d{4})\b'
      flags: IGNORECASE
      expansions:
        - "{prefix}_law_{num}_{year}"
    - name: "schedule_ref"
      pattern: '\b(?:Schedule)\s+(?P<id>\w+)\b'
      flags: IGNORECASE
      expansions:
        - "schedule_{id}"
    - name: "regulation_ref"
      pattern: '\b(?:Regulation)\s+(?P<parts>\d+(?:\.\d+)*)\b'
      flags: IGNORECASE
      expansions:
        - "regulation_{parts}"   # dots replaced with underscores at runtime

# ---------------------------------------------------------------
# Embedding decontamination (boilerplate to strip before embedding)
# ---------------------------------------------------------------
boilerplate_patterns:
  - 'IN\s+THE\s+DUBAI\s+INTERNATIONAL\s+FINANCIAL\s+CENTRE\s+COURTS?'
  - 'IN\s+THE\s+COURT\s+OF\s+FIRST\s+INSTANCE'
  - 'IN\s+THE\s+SMALL\s+CLAIMS\s+TRIBUNAL'
  - 'COURT\s+OF\s+APPEAL'
  - '(?:Claim|Case)\s+No\s*:\s*\S+'
  - '^BETWEEN\s*$'
  - '^(?:Claimant|Defendant|Respondent|Applicant)s?\s*$'
  - 'Page\s+\d+\s+of\s+\d+'
  - '^\s*\d{1,3}\s*$'
  - '^\s*\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}\s*$'

# ---------------------------------------------------------------
# System prompts (per answer_type)
# ---------------------------------------------------------------
prompts:
  expert_role: "You are an expert in Dubai International Financial Centre (DIFC) laws and regulations."
  jurisdiction_context: "The DIFC Courts operate as a civil and commercial jurisdiction under DIFC Law No. 10 of 2004."

  boolean: |
    {expert_role} Answer ONLY based on the provided documents.
    Output ONLY: true, false, or null.
    - true: the statement is supported by the documents
    - false: the statement is contradicted by the documents
    - null: the documents do not contain enough information
    Your first line must be: true, false, or null.

  number: |
    {expert_role} Extract the exact numeric value from the provided documents.
    Output ONLY the number (integer or decimal). No currency, no units, no text.
    If not found, output: null
    Your first line must be: the number or null.

  name: |
    {expert_role} Extract the exact name requested from the provided documents.
    Output ONLY the name exactly as it appears in the document.
    If not found, output: null
    Your first line must be: the name or null.

  names: |
    {expert_role} Extract the list of names requested from the provided documents.
    Output ONLY comma-separated names exactly as they appear.
    If not found, output: null

  date: |
    {expert_role} Extract the exact date from the provided documents.
    Output ONLY in ISO 8601 format: YYYY-MM-DD
    If not found, output: null

  free_text_law: |
    You are a {short_name} legal expert writing precise answers for a professional legal QA evaluation.
    ... (full prompt template with {short_name} and {jurisdiction_context} placeholders)

  free_text_case: |
    You are a {short_name} legal expert writing precise answers about {short_name} court case outcomes.
    ... (full prompt template)

  free_text_trick: |
    You are a {short_name} legal expert. {jurisdiction_context}
    Write a confident answer explaining why the asked concept does not exist in {short_name}.

  # Name comparison sub-prompts
  name_date_compare: |
    You are an expert legal document analyst specializing in {short_name} cases.
    For this date comparison question, follow these steps EXACTLY: ...

  name_value_compare: |
    You are an expert legal document analyst specializing in {short_name} cases.
    For this value comparison question, follow these steps EXACTLY: ...

# ---------------------------------------------------------------
# Trick question detection (jurisdiction-specific)
# ---------------------------------------------------------------
trick_questions:
  enabled: true
  # Exact keyword matches (always trigger, even with case ID in question)
  keywords:
    - "miranda"
    - "miranda rights"
    - "grand jury"
    - "trial by jury"
    - "plea bargain"
    - "parole"
    - "habeas corpus"
    - "felony"
    - "misdemeanor"
    - "criminal jurisdiction"
    # ... (full list)

  # Regex patterns for broader detection
  regex_patterns:
    - '\bcriminal\s+\w+'
    - '\bconvicted\s+of\b'
    - '\bjury\b'
    - '\bprosecutor\b'
    - '\bprison\b'

  # Template for the trick answer
  answer_template: >
    There is no information on this question in the provided documents.
    The {short_name} Courts operate exclusively as a civil and commercial
    jurisdiction and do not have criminal jurisdiction.

  # Pattern to detect case IDs (suppresses Level 2/3 trick detection)
  case_id_safety_pattern: '(?:CFI|SCT|CA|ARB|ENF|DEC|TCD|ACT)\s*[\-]?\s*\d+\s*(?:/|\s+of\s+)\d{4}'

# ---------------------------------------------------------------
# Retrieval tuning
# ---------------------------------------------------------------
retrieval:
  # Identifier extraction patterns for keyword-based doc finding
  identifier_patterns:
    - '(?:case\s+no\.?\s*|case\s+|no\.\s*)((?:CFI|CA|ARB|ENF|SCT|TCD|DEC)[\s\-_]*\d+[\s/\-_]*\d+)'
    - '(?:CFI|CA|ARB|ENF|SCT|TCD|DEC)[\s\-_]*\d+[\s/\-_]*\d+'
    - 'Law\s+No\.?\s*\d+\s+of\s+\d+'
    - 'DIFC\s+Law\s+No\.?\s*\d+(?:\s+of\s+\d+)?'
    - 'Regulation\s+No\.?\s*\d+'
    - '"([^"]+)"'

  # HyDE prompt template
  hyde_prompt: >
    Write a single concise paragraph (3-4 sentences) from a {short_name} legal document
    that directly answers this question: {question}
    Write only the document text, no preamble.

  # Consultation paper patterns (DIFC-specific; other domains may not have these)
  consultation_paper_pattern: '[Cc]onsultation\s+[Pp]aper\s+(?:[Nn]o\.?\s*)?(\d+)(?:\s+of\s+(\d{4}))?'

  # Court order patterns
  court_order_patterns:
    - pattern: '(?:DIFC\s+)?Courts?\s+(?:(?:Rules\s+of\s+Court\s+)|(?:Small\s+Claims\s+(?:Tribunal|Leasing\s+Tribunal)\s+))?Order\s+No\.?\s*(\d+)\s+of\s+(\d{4})'
      flags: IGNORECASE
    - pattern: 'DRA\s+Order\s+No\.?\s*(\d+)\s+of\s+(\d{4})'
      flags: IGNORECASE

  # Enactment keywords
  enactment_keywords:
    - "enactment"
    - "enacted"
    - "come into force"
    - "effective date"
    - "commencement date"

# ---------------------------------------------------------------
# Plugin configuration
# ---------------------------------------------------------------
plugin:
  module: "arlc.plugins.difc"
  class: "DIFCPlugin"
```

### 2.2 Example: US Federal Courts Domain

```yaml
domain:
  id: "us_federal"
  name: "United States Federal Courts"
  short_name: "US Federal"
  description: "US federal court system including district, circuit, and Supreme Court"

document_types:
  case:
    label: "Federal Case"
    id_patterns:
      # "No. 23-1234" / "Case No. 2:23-cv-01234"
      - pattern: '(?:No\.\s*)?(?P<prefix>\d+):(?P<number>\d{2}-(?:cv|cr|mc|ap)-\d{4,6})'
        flags: IGNORECASE
        normalize: "{prefix}:{number}"
      # Circuit court: "23-1234"
      - pattern: '(?P<number>\d{2}-\d{4,5})'
        normalize: "{number}"
      # Supreme Court: "No. 22-451"
      - pattern: '(?:No\.\s*)(?P<number>\d{2}-\d{2,4})'
        normalize: "{number}"
    metadata_fields:
      filing_date:
        type: date
        indicators:
          - 'fil(?:ed|ing)\s+date'
          - 'date\s+(?:of\s+)?fil(?:ed|ing)'
      judge:
        type: name
        default_page: 1
        indicators:
          - '(?:the\s+)?(?:Honorable\s+)?Judge'
          - '(?:presiding|assigned)\s+judge'
          - '(?:Chief\s+)?(?:Justice|Judge|Magistrate)'
      parties:
        type: names
        default_page: 1
        indicators:
          - '(?:plaintiff|defendant|petitioner|respondent|appellant|appellee)'
      jurisdiction:
        type: name
        indicators:
          - '(?:subject.matter|personal|diversity)\s+jurisdiction'
    sac_keywords:
      - "court opinion"
      - "memorandum opinion"
      - "order"

  statute:
    label: "Federal Statute"
    sac_keywords:
      - "united states code"
      - "public law"
      - "u.s.c."

  regulation:
    label: "Federal Regulation"
    sac_keywords:
      - "code of federal regulations"
      - "c.f.r."
      - "federal register"

law_names:
  extraction_patterns:
    - '(?:the\s+)?(?:Federal\s+)?(?P<name>[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+Act(?:\s+of\s+\d{4})?'
    - '(?:\d+)\s+U\.?S\.?C\.?\s+(?:(?:Section|\x{00A7})\s*)?(?P<section>\d+)'
    - '(?:\d+)\s+C\.?F\.?R\.?\s+(?:Part\s+)?(?P<part>\d+(?:\.\d+)?)'
  strip_prefixes: ["the ", "federal "]
  abbreviations:
    ada: "Americans with Disabilities Act"
    foia: "Freedom of Information Act"
    rico: "Racketeer Influenced and Corrupt Organizations Act"
    flsa: "Fair Labor Standards Act"
  short_names: {}
  number_map: {}
  known_names:
    - "Americans with Disabilities Act"
    - "Civil Rights Act"
    - "Clean Air Act"
    - "Fair Labor Standards Act"
    - "Freedom of Information Act"

tokenizer:
  patterns:
    - name: "case_number"
      pattern: '\b(?P<prefix>\d+):(?P<number>\d{2}-\w{2}-\d{4,6})\b'
      expansions:
        - "{prefix}_{number}"
    - name: "usc_ref"
      pattern: '(?P<title>\d+)\s+U\.?S\.?C\.?\s+(?:(?:Section|\x{00A7})\s*)?(?P<section>\d+)'
      expansions:
        - "usc_{title}_{section}"
        - "{title}_usc_{section}"
    - name: "cfr_ref"
      pattern: '(?P<title>\d+)\s+C\.?F\.?R\.?\s+(?:Part\s+)?(?P<part>\d+(?:\.\d+)?)'
      expansions:
        - "cfr_{title}_{part}"

boilerplate_patterns:
  - 'UNITED\s+STATES\s+(?:DISTRICT|CIRCUIT|BANKRUPTCY)\s+COURT'
  - 'FOR\s+THE\s+(?:NORTHERN|SOUTHERN|EASTERN|WESTERN)\s+DISTRICT\s+OF'
  - '(?:Case|Docket)\s+No\.?\s*:?\s*\S+'
  - 'MEMORANDUM\s+(?:OPINION|ORDER|AND\s+ORDER)'
  - '^\s*\d+\s*$'

prompts:
  expert_role: "You are an expert in United States federal law and court procedure."
  jurisdiction_context: "The US federal court system operates under Article III of the Constitution."

  boolean: |
    {expert_role} Answer ONLY based on the provided documents.
    Output ONLY: true, false, or null.
    Your first line must be: true, false, or null.

  number: |
    {expert_role} Extract the exact numeric value from the provided documents.
    Output ONLY the number. If not found, output: null

  free_text_law: |
    You are a {short_name} legal expert writing precise answers for a professional legal QA evaluation.
    ...

trick_questions:
  enabled: false   # US Federal has criminal jurisdiction; no trick questions needed

retrieval:
  identifier_patterns:
    - '(?:No\.\s*)?\d+:\d{2}-\w{2}-\d{4,6}'
    - '\d{2}-\d{4,5}'
    - '\d+\s+U\.?S\.?C\.?\s+(?:Section\s*)?\d+'
    - '\d+\s+C\.?F\.?R\.?\s+(?:Part\s*)?\d+'
    - '"([^"]+)"'
  hyde_prompt: >
    Write a single concise paragraph from a US federal court opinion or statute
    that directly answers this question: {question}
  consultation_paper_pattern: null   # Not applicable
  court_order_patterns: []
  enactment_keywords:
    - "enacted"
    - "effective date"
    - "signed into law"

plugin:
  module: "arlc.plugins.us_federal"
  class: "USFederalPlugin"
```

### 2.3 Example: UK Contract Law Domain

```yaml
domain:
  id: "uk_contracts"
  name: "United Kingdom Contract Law"
  short_name: "UK Contract"
  description: "UK contract law including common law and statutory provisions"

document_types:
  case:
    label: "Court Case"
    id_patterns:
      # "[2024] EWHC 1234 (Comm)" / "[2024] UKSC 12"
      - pattern: '\[(?P<year>\d{4})\]\s+(?P<prefix>EWHC|EWCA|UKSC|UKPC|UKUT)\s+(?P<number>\d+)(?:\s+\((?P<division>\w+)\))?'
        normalize: "[{year}] {prefix} {number}"
      # Older style: "Smith v Jones [2020] 1 AC 123"
      - pattern: '\[(?P<year>\d{4})\]\s+(?P<volume>\d+)\s+(?P<report>AC|QB|Ch|WLR|All\s+ER)\s+(?P<page>\d+)'
        normalize: "[{year}] {volume} {report} {page}"
    metadata_fields:
      date_of_judgment:
        type: date
        indicators:
          - 'date\s+of\s+(?:judgment|decision|hearing)'
          - 'judgment\s+(?:handed\s+)?down\s+on'
      judge:
        type: name
        default_page: 1
        indicators:
          - '(?:Lord|Lady|Mr|Mrs)\s+Justice'
          - '(?:His|Her)\s+Honour\s+Judge'
      parties:
        type: names
        default_page: 1
        indicators:
          - '(?:claimant|defendant|appellant|respondent)'
          - '(?:between|and)\s+.*(?:claimant|defendant)'

  statute:
    label: "Act of Parliament"
    sac_keywords:
      - "act of parliament"
      - "statutory instrument"

law_names:
  extraction_patterns:
    - '(?:the\s+)?(?P<name>[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+Act\s+(?P<year>\d{4})'
    - '(?:Section|s\.?)\s+(?P<section>\d+)(?:\((?P<subsection>\d+)\))?'
  strip_prefixes: ["the "]
  abbreviations:
    sga: "Sale of Goods Act 1979"
    cra: "Consumer Rights Act 2015"
    ucta: "Unfair Contract Terms Act 1977"
  known_names:
    - "Sale of Goods Act 1979"
    - "Consumer Rights Act 2015"
    - "Unfair Contract Terms Act 1977"
    - "Misrepresentation Act 1967"
    - "Contracts (Rights of Third Parties) Act 1999"
    - "Supply of Goods and Services Act 1982"

tokenizer:
  patterns:
    - name: "case_citation"
      pattern: '\[(?P<year>\d{4})\]\s+(?P<prefix>EWHC|EWCA|UKSC)\s+(?P<number>\d+)'
      expansions:
        - "{prefix}_{number}_{year}"
    - name: "section_ref"
      pattern: '(?:Section|s\.?)\s+(?P<num>\d+)(?:\((?P<sub>\d+)\))?'
      flags: IGNORECASE
      expansions:
        - "section_{num}"
        - "section_{num}_{sub}"

boilerplate_patterns:
  - 'IN\s+THE\s+(?:HIGH\s+COURT|SUPREME\s+COURT|COURT\s+OF\s+APPEAL)'
  - 'QUEEN.S\s+BENCH\s+DIVISION|KING.S\s+BENCH\s+DIVISION'
  - 'CHANCERY\s+DIVISION'
  - '(?:Claim|Case)\s+No\.?\s*:?\s*\S+'
  - 'Approved\s+Judgment'
  - '^\s*\d+\s*$'

prompts:
  expert_role: "You are an expert in English contract law."
  jurisdiction_context: "English contract law is governed by common law principles and key statutes."

  boolean: |
    {expert_role} Answer ONLY based on the provided documents.
    Output ONLY: true, false, or null.

  free_text_law: |
    You are an {short_name} law expert writing precise answers.
    Cite specific sections and leading cases where applicable.
    ...

trick_questions:
  enabled: false   # UK has criminal jurisdiction; no blanket trick detection

retrieval:
  identifier_patterns:
    - '\[\d{4}\]\s+(?:EWHC|EWCA|UKSC|UKPC)\s+\d+'
    - '(?:Section|s\.?)\s+\d+(?:\(\d+\))?'
    - '"([^"]+)"'
  hyde_prompt: >
    Write a single concise paragraph from an English law judgment or statute
    that directly answers this question: {question}

plugin:
  module: "arlc.plugins.uk_contracts"
  class: "UKContractsPlugin"
```

## 3. Module-by-Module Changes

### 3.1 New: `arlc/domain.py` (DomainConfig loader)

New file. Loads the YAML config at startup, compiles regex patterns, exposes typed accessors.

```python
# Pseudocode
class DomainConfig:
    """Singleton that loads and serves domain configuration."""

    _instance = None

    @classmethod
    def load(cls, domain_id: str = None) -> "DomainConfig":
        if cls._instance is None:
            domain_id = domain_id or os.environ.get("ARLC_DOMAIN", "difc")
            path = Path(__file__).parent.parent / "domains" / f"{domain_id}.yaml"
            cls._instance = cls(yaml.safe_load(path.read_text()))
        return cls._instance

    # Typed accessors:
    @property
    def case_id_patterns(self) -> list[CompiledPattern]: ...
    @property
    def law_name_patterns(self) -> list[re.Pattern]: ...
    @property
    def system_prompt(self, answer_type: str) -> str: ...
    @property
    def boilerplate_patterns(self) -> list[re.Pattern]: ...
    @property
    def trick_keywords(self) -> list[str]: ...
    # etc.
```

**Effort: ~0.5 day**

### 3.2 `arlc/router.py` -- Hardcoded Patterns to Config

**Current DIFC-specific code (with line numbers):**

| Lines   | What                                         | Change                                                                      |
|---------|----------------------------------------------|-----------------------------------------------------------------------------|
| 22-25   | `CASE_ID_PATTERN` hardcoded regex            | Read from `config.document_types.case.id_patterns`                          |
| 28-31   | `BARE_CASE_ID_PATTERN`                       | Read from config (entries with `type: "bare"`)                              |
| 58-62   | `CONSULTATION_PAPER_PATTERN`                 | Read from `config.retrieval.consultation_paper_pattern`                     |
| 65-73   | `COURT_ORDER_PATTERN`, `DRA_ORDER_PATTERN`   | Read from `config.retrieval.court_order_patterns`                           |
| 76-109  | `CP_TOPIC_KEYWORDS` dict                     | Move to config or plugin (DIFC-specific complex logic)                      |
| 117-121 | `DIFC_LAW_NO_PATTERN`                        | Read from `config.law_names.number_pattern`                                 |
| 124-168 | `LAW_NAME_PATTERNS` list of regexes          | Read from `config.law_names.extraction_patterns`                            |
| 170-217 | `METADATA_INDICATORS` dict                   | Read from `config.document_types.case.metadata_fields[*].indicators`        |
| 235-236 | `Router.__init__` class docstring "for DIFC" | Parameterize                                                                |
| 289-335 | `_extract_case_ids()`                        | Generalize normalization using `normalize` and `normalize_alts` from config |
| 337-494 | `_extract_law_names()`                       | Use config patterns, abbreviations, short_names, number_map                 |
| 399-408 | `canonical_short` dict                       | Read from `config.law_names.short_names`                                    |
| 418-428 | `abbrev_law_pairs`                           | Read from `config.law_names.abbreviations`                                  |
| 435-449 | `difc_law_map` (law_no -> name)              | Read from `config.law_names.number_map`                                     |
| 921     | `"these Regulations"` detection              | Keep generic (applies to any regulatory domain)                             |
| 939-954 | Amendment question detection                 | Keep generic (pattern is jurisdiction-agnostic)                             |

**Approach:** `Router.__init__` takes a `DomainConfig` parameter. All patterns are compiled from config at init time.
The `route()` method logic stays the same -- only the patterns it matches against change.

**Effort: ~1.5 days**

### 3.3 `arlc/retriever.py` -- Law Names and Identifiers

**Current DIFC-specific code:**

| Lines   | What                                                                         | Change                                                                                       |
|---------|------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------|
| 361-395 | `_DIFC_LAW_NAMES` list                                                       | Read from `config.law_names.known_names`                                                     |
| 398-428 | `extract_identifiers()` -- hardcoded case ID regexes + `_DIFC_LAW_NAMES`     | Read patterns from `config.retrieval.identifier_patterns` and `config.law_names.known_names` |
| 431-506 | `_score_doc_by_law_name()` -- SAC prefix matching ("difc law", "court case") | Read from `config.document_types[*].sac_keywords`                                            |
| 509-598 | `find_docs_by_keyword()` -- case pattern with CFI/SCT/etc prefixes           | Read from `config.document_types.case.id_patterns`                                           |
| 546-565 | Partial match case patterns (CFI, CA, ARB, ENF, SCT, TCD, DEC)               | Extract prefixes from config patterns                                                        |
| 567-578 | Enactment keyword search                                                     | Read from `config.retrieval.enactment_keywords`                                              |
| 648-656 | CE query cleaning (DIFC-specific long case name regex)                       | Move regex to config or plugin                                                               |
| 970     | HyDE prompt: "from a DIFC legal document"                                    | Read from `config.retrieval.hyde_prompt`                                                     |

**Approach:** Module-level `_DIFC_LAW_NAMES` replaced by `DomainConfig.get().law_names.known_names`. Functions like
`extract_identifiers()` iterate over config-provided patterns. The hybrid retrieval logic (BM25 + vector +
cross-encoder) is generic and stays unchanged.

**Effort: ~1 day**

### 3.4 `arlc/answerer.py` -- Prompt Templates

**Current DIFC-specific code:**

| Lines     | What                                                       | Change                                             |
|-----------|------------------------------------------------------------|----------------------------------------------------|
| 117-126   | `_SYSTEM_BOOLEAN` -- "expert in DIFC laws"                 | Read from `config.prompts.boolean`                 |
| 128-133   | `_SYSTEM_NUMBER`                                           | Read from `config.prompts.number`                  |
| 135-140   | `_SYSTEM_NAME`                                             | Read from `config.prompts.name`                    |
| 142-155   | `_SYSTEM_NAME_DATE_COMPARE`                                | Read from `config.prompts.name_date_compare`       |
| 157-171   | `_SYSTEM_NAME_VALUE_COMPARE`                               | Read from `config.prompts.name_value_compare`      |
| 173-177   | `_SYSTEM_NAMES`                                            | Read from `config.prompts.names`                   |
| 179-184   | `_SYSTEM_DATE`                                             | Read from `config.prompts.date`                    |
| 187-238   | `_SYSTEM_FREE_TEXT_LAW`                                    | Read from `config.prompts.free_text_law`           |
| 241-282   | `_SYSTEM_FREE_TEXT_CASE`                                   | Read from `config.prompts.free_text_case`          |
| 284-286   | `_SYSTEM_FREE_TEXT_TRICK`                                  | Read from `config.prompts.free_text_trick`         |
| 288-295   | `_CASE_ID_PATTERN`, `_CASE_KEYWORDS`                       | Read from config patterns                          |
| 297-326   | `_TRICK_KEYWORDS`                                          | Read from `config.trick_questions.keywords`        |
| 861-865   | Trick answer inline text referencing DIFC                  | Read from `config.trick_questions.answer_template` |
| 1808      | Law identification heuristics (trust -> "trust law", etc.) | Read from `config.law_names.short_names`           |
| 1866-1878 | `_identify_law()` keyword lists                            | Read from config                                   |
| 2058      | "COMPLETE text of the relevant DIFC Law"                   | Template with `{short_name}`                       |

**Approach:** All `_SYSTEM_*` variables become properties of `DomainConfig` with `{expert_role}`, `{short_name}`,
`{jurisdiction_context}` placeholders resolved at load time. The answer generation logic itself (LLM call, parsing,
retry) is generic.

**Effort: ~1 day**

### 3.5 `arlc/indexing/legal_tokenizer.py` -- Token Patterns

**Current DIFC-specific code:**

| Lines  | What                                    | Change                                                  |
|--------|-----------------------------------------|---------------------------------------------------------|
| 14-16  | `_CASE_ID_RE` -- hardcoded `[A-Z]{2,5}` | Read from `config.tokenizer.patterns`                   |
| 19-21  | `_ENF_RE` -- ENF-specific               | Becomes one of the config patterns                      |
| 24-31  | `_ARTICLE_RE`, `_LAW_NO_RE`             | Read from config patterns                               |
| 34-41  | `_SCHEDULE_RE`, `_REGULATION_RE`        | Read from config patterns                               |
| 55-106 | `_expand_legal_refs()`                  | Iterate over config patterns, apply expansion templates |

**Approach:** `_expand_legal_refs()` becomes a generic function that iterates over `config.tokenizer.patterns`, applies
each regex, and generates expansion tokens from the template strings. The template language supports `{group_name}`
substitution and conditional inclusion (only expand if group was captured).

**Effort: ~0.5 day**

### 3.6 `arlc/indexing/indexer.py` -- Boilerplate Patterns

**Current DIFC-specific code:**

| Lines | What                         | Change                                  |
|-------|------------------------------|-----------------------------------------|
| 37-48 | `_BOILERPLATE_PATTERNS` list | Read from `config.boilerplate_patterns` |

This is a straightforward replacement. The `clean_text_for_embedding()` function already takes a list of patterns -- it
just needs to read them from config instead of module-level constants.

**Effort: ~0.25 day**

### 3.7 `arlc/pipeline.py` -- Trick Questions and Post-Processing

**Current DIFC-specific code:**

| Lines   | What                       | Change                                                    |
|---------|----------------------------|-----------------------------------------------------------|
| 186-235 | `_TRICK_KEYWORDS` list     | Read from `config.trick_questions.keywords`               |
| 239-248 | `_CRIMINAL_PREFIX_RE`      | Read from `config.trick_questions.regex_patterns`         |
| 252-280 | `_is_trick_question()`     | Use config for keywords, regexes, case_id_safety_pattern  |
| 271     | Case ID safety guard regex | Read from `config.trick_questions.case_id_safety_pattern` |
| 718     | Trick answer text          | Read from `config.trick_questions.answer_template`        |

**Effort: ~0.5 day**

### 3.8 `arlc/page_verifier.py` -- No Changes

This module is already fully generic. It works with answer types, keywords, and page text without any
jurisdiction-specific logic.

### 3.9 New: `arlc/plugins/base.py` (Plugin Interface)

```python
from abc import ABC, abstractmethod

class DomainPlugin(ABC):
    """Interface for domain-specific logic that can't be expressed in config."""

    def post_route(self, route_result, question: str, answer_type: str):
        """Hook after routing, before retrieval. Can modify route_result."""
        return route_result

    def post_retrieve(self, pages: list, question: str, answer_type: str):
        """Hook after retrieval, before answering. Can modify pages."""
        return pages

    def post_answer(self, answer_result, question: str, answer_type: str):
        """Hook after answer generation. Can modify answer."""
        return answer_result

    def resolve_consultation_paper(self, question: str) -> list[str]:
        """Domain-specific document resolution for special doc types."""
        return []

    def get_topic_keywords(self) -> dict[str, list[str]]:
        """Return topic keyword map for document disambiguation."""
        return {}
```

### 3.10 New: `arlc/plugins/difc.py` (DIFC Plugin)

Houses complex DIFC logic that cannot be expressed purely in config:

- `CP_TOPIC_KEYWORDS` mapping and the `_build_cp_topic_map()` logic (reads PDFs, matches topics)
- Consultation paper disambiguation by topic
- Court order type inference from context ("rules of court" vs "sct" vs "court")
- Appeal cross-reference logic (SCT -> CFI appeal documents)
- The `difc_law_map` number-to-name lookup (complex tuple-keyed dict)

**Effort: ~0.5 day**

## 4. Data Files

Data files (`data/*.json`) are already domain-specific by nature. The config simply declares which index files to load:

```yaml
# In domains/difc.yaml
data_indices:
  case_metadata: "data/case_metadata_index.json"
  article_pages: "data/article_page_index.json"
  law_names: "data/law_name_index.json"
  latest_editions: "data/latest_edition_index.json"
  consultation_papers: "data/consultation_paper_index.json"
  court_orders: "data/court_order_index.json"
  appeals: "data/appeal_index.json"
```

For a new domain, you would build equivalent index files from the new corpus. The indexing tools (`build_index()`,
metadata extraction scripts) would need to understand the domain's document structure -- this is where plugins provide
custom extraction logic.

## 5. Migration Path

### Phase 1: Extract config (no behavior change) -- 2-3 days

1. Create `domains/difc.yaml` with all current hardcoded values
2. Create `arlc/domain.py` with the config loader
3. Modify each module to read from `DomainConfig` instead of module-level constants
4. Run full test suite -- output must be bit-identical to current pipeline
5. Create `arlc/plugins/difc.py` for complex DIFC logic

### Phase 2: Validate with DIFC -- 1 day

1. Run the full warmup dataset with config-driven pipeline
2. Verify scores match: S_det, S_asst, G, F must be identical
3. Profile for any performance regression from config loading

### Phase 3: Add second domain -- 2-3 days per domain

1. Create `domains/<domain>.yaml`
2. Build corpus indices (case_metadata, law_names, article_pages, etc.)
3. Write domain plugin if needed
4. Test with domain-specific QA pairs

## 6. Example: Adding "US Federal Courts" Domain

| Step                                | Work                                                                                                                                  | Time          |
|-------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------|---------------|
| 1. Create `domains/us_federal.yaml` | Write config with US case patterns, statutes, CFR refs                                                                                | 4 hours       |
| 2. Build data indices               | Run indexer on federal corpus; build `case_metadata_index.json` (judges, dates, parties) and `law_name_index.json` (USC/CFR mappings) | 8 hours       |
| 3. Write prompts                    | Adapt free_text prompts for federal legal style; adjust calibration examples                                                          | 4 hours       |
| 4. Write plugin (if needed)         | USC cross-reference resolution, circuit/district disambiguation                                                                       | 4 hours       |
| 5. Test and tune                    | Run evaluation dataset, tune retrieval boosts, cross-encoder thresholds                                                               | 8 hours       |
| **Total**                           |                                                                                                                                       | **~3.5 days** |

**What stays untouched:** BM25 indexing, FAISS/ChromaDB vector store, cross-encoder reranking, page verification, format
guardian, LLM call infrastructure, parallel worker pipeline.

## 7. Example: Adding "UK Contract Law" Domain

| Step                                  | Work                                                                 | Time          |
|---------------------------------------|----------------------------------------------------------------------|---------------|
| 1. Create `domains/uk_contracts.yaml` | EWHC/EWCA/UKSC patterns, Section refs, Act patterns                  | 3 hours       |
| 2. Build data indices                 | Index contract law cases and statutes; build metadata                | 6 hours       |
| 3. Write prompts                      | Contract law expertise, English legal terminology                    | 3 hours       |
| 4. Write plugin (minimal)             | Neutral citation resolution, statute section cross-refs              | 2 hours       |
| 5. Disable trick questions            | UK has criminal jurisdiction -- set `trick_questions.enabled: false` | 0.25 hours    |
| 6. Test and tune                      |                                                                      | 6 hours       |
| **Total**                             |                                                                      | **~2.5 days** |

## 8. Estimated Total Effort

| Component                                       | Effort        |
|-------------------------------------------------|---------------|
| `arlc/domain.py` (config loader)                | 0.5 day       |
| `arlc/plugins/base.py` + `difc.py`              | 0.5 day       |
| `arlc/router.py` refactor                       | 1.5 days      |
| `arlc/retriever.py` refactor                    | 1 day         |
| `arlc/answerer.py` refactor                     | 1 day         |
| `arlc/indexing/legal_tokenizer.py` refactor     | 0.5 day       |
| `arlc/indexing/indexer.py` refactor             | 0.25 day      |
| `arlc/pipeline.py` refactor                     | 0.5 day       |
| `domains/difc.yaml` creation                    | 0.5 day       |
| Integration testing (bit-identical validation)  | 1 day         |
| **Total Phase 1+2 (config-driven DIFC)**        | **~7 days**   |
| **Each new domain (config + indices + tuning)** | **~2-4 days** |

## 9. Key Design Decisions

1. **YAML over JSON** for config: YAML supports comments, multi-line strings (prompts), and is more readable for complex
   legal patterns.

2. **Plugin system over config-only**: Some DIFC logic (CP topic disambiguation, appeal cross-referencing) involves
   reading PDF content at init time and maintaining runtime state. This is fundamentally procedural and does not reduce
   well to declarative config. The plugin interface provides clean hooks without polluting the generic pipeline.

3. **Singleton DomainConfig**: Loaded once at startup, immutable thereafter. Thread-safe. No per-request overhead.

4. **Prompt template variables**: Simple `{variable}` substitution (not Jinja2) to keep dependencies minimal and prompts
   auditable. Variables: `{expert_role}`, `{short_name}`, `{jurisdiction_context}`, `{question}`.

5. **Backward compatibility**: The DIFC config should reproduce the exact current behavior. The `ARLC_DOMAIN` env var
   defaults to `"difc"`, so existing deployments work without changes.

6. **Index files per domain**: Stored in `data/<domain>/` subdirectories. The generic pipeline reads paths from config,
   not hardcoded `data/` paths.
