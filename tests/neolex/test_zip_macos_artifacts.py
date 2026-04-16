"""Unit tests for ZIP extraction — macOS artifact handling.

Verifies that __MACOSX/ entries, .DS_Store files, and ._* resource forks
are silently dropped (not counted in skipped_files), while legitimate
non-PDF/TXT files are properly counted as skipped.

No database or network access is needed.
"""

from __future__ import annotations

import io
import zipfile

from neolex.services.document_manager import extract_zip_safely

# ---------------------------------------------------------------------------
# PDF magic bytes stub — minimal but valid-looking PDF
# ---------------------------------------------------------------------------

_PDF_STUB = b"%PDF-1.4\n%%EOF\n"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_zip(*entries: tuple[str, bytes]) -> bytes:
    """Build an in-memory ZIP containing the given (name, content) pairs."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in entries:
            zf.writestr(name, content)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMacOSArtifacts:
    def test_macosx_artifacts_silently_skipped(self):
        """__MACOSX/, .DS_Store, and ._* entries are dropped without appearing in skipped_files."""
        zb = _make_zip(
            ("__MACOSX/._realfile.pdf", b"resource fork garbage"),
            (".DS_Store", b"macOS metadata"),
            ("realfile.pdf", _PDF_STUB),
        )

        valid_files, skipped_files = extract_zip_safely(zb)

        assert len(valid_files) == 1, f"Expected 1 valid file, got {len(valid_files)}: {valid_files}"
        assert valid_files[0][0] == "realfile.pdf"

        # macOS artifacts must NOT appear in skipped_files — they are silently dropped
        assert len(skipped_files) == 0, f"macOS artifacts must not appear in skipped_files, but got: {skipped_files}"

    def test_dot_underscore_resource_fork_silently_skipped(self):
        """._<name> resource fork files outside __MACOSX/ are also silently dropped."""
        zb = _make_zip(
            ("._contract.pdf", b"resource fork"),
            ("contract.pdf", _PDF_STUB),
        )

        valid_files, skipped_files = extract_zip_safely(zb)

        assert len(valid_files) == 1
        assert valid_files[0][0] == "contract.pdf"
        assert len(skipped_files) == 0, f"._* files should be silent, got: {skipped_files}"

    def test_non_pdf_txt_counted_as_skipped(self):
        """A .docx file (not a macOS artifact) IS added to skipped_files with the correct reason."""
        zb = _make_zip(
            ("contract.docx", b"PK\x03\x04fake docx content"),
        )

        valid_files, skipped_files = extract_zip_safely(zb)

        assert len(valid_files) == 0
        assert len(skipped_files) == 1, f"Expected 1 skipped file, got: {skipped_files}"
        skipped_name, skipped_reason = skipped_files[0]
        assert skipped_name == "contract.docx"
        assert skipped_reason == "skipped_unsupported_format"

    def test_mixed_artifacts_and_real_files(self):
        """Mixed ZIP: real PDF accepted, macOS artifacts silent, unsupported format counted."""
        zb = _make_zip(
            ("__MACOSX/._notes.txt", b"mac resource fork"),
            (".DS_Store", b"mac store"),
            ("notes.txt", b"This is a legal text document.\n"),
            ("presentation.pptx", b"PK\x03\x04fake pptx"),
        )

        valid_files, skipped_files = extract_zip_safely(zb)

        valid_names = {name for name, _ in valid_files}
        assert "notes.txt" in valid_names
        assert len(valid_files) == 1

        # Only the .pptx should be in skipped_files
        assert len(skipped_files) == 1
        assert skipped_files[0][0] == "presentation.pptx"
        assert skipped_files[0][1] == "skipped_unsupported_format"
