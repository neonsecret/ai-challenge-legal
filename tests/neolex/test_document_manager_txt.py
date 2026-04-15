"""Unit tests for TXT-file support in neolex.services.document_manager.

Tests save_upload(), extract_zip_safely(), and _is_valid_text_content()
without hitting the database or network.  Uses pytest's tmp_path fixture
to isolate filesystem writes.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from neolex.services.document_manager import (
    _is_valid_text_content,
    extract_zip_safely,
    save_upload,
)

# ---------------------------------------------------------------------------
# Stubs
# ---------------------------------------------------------------------------

_PDF_STUB = b"%PDF-1.4\n%%EOF\n"
_TXT_STUB = b"This is a sample legal text document.\n"
_BINARY_STUB = b"Not text\x00binary garbage"


# ---------------------------------------------------------------------------
# _is_valid_text_content
# ---------------------------------------------------------------------------


class TestIsValidTextContent:
    def test_valid_utf8_returns_true(self):
        assert _is_valid_text_content(b"Hello, world!\n") is True

    def test_empty_bytes_returns_true(self):
        # Empty TXT is caught by the empty-file guard upstream; content itself is "valid"
        assert _is_valid_text_content(b"") is True

    def test_null_byte_returns_false(self):
        assert _is_valid_text_content(b"text\x00here") is False

    def test_invalid_utf8_sequence_returns_false(self):
        assert _is_valid_text_content(b"\xff\xfe invalid") is False

    def test_czech_legal_text_returns_true(self):
        czech = "Zákon č. 89/2012 Sb., občanský zákoník".encode("utf-8")
        assert _is_valid_text_content(czech) is True

    def test_pdf_magic_bytes_returns_false(self):
        # PDF starts with %PDF — binary after that causes UTF-8 decode failure
        assert _is_valid_text_content(_PDF_STUB + b"\x00") is False


# ---------------------------------------------------------------------------
# save_upload — PDF path (regression guard)
# ---------------------------------------------------------------------------


class TestSaveUploadPDF:
    def test_valid_pdf_is_saved_with_pdf_extension(self, tmp_path: Path):
        with patch("neolex.services.document_manager.settings") as mock_settings:
            mock_settings.data_dir = str(tmp_path)
            meta = save_upload("client1", "contract.pdf", _PDF_STUB)

        assert meta["filename"].endswith(".pdf")
        assert meta["file_type"] == "pdf"
        assert meta["size_bytes"] == len(_PDF_STUB)
        assert Path(meta["path"]).exists()

    def test_non_pdf_magic_bytes_raises(self, tmp_path: Path):
        with patch("neolex.services.document_manager.settings") as mock_settings:
            mock_settings.data_dir = str(tmp_path)
            with pytest.raises(ValueError, match="Not a valid PDF"):
                save_upload("client1", "fake.pdf", b"This is not a PDF")

    def test_oversized_content_raises(self, tmp_path: Path):
        with patch("neolex.services.document_manager.settings") as mock_settings:
            mock_settings.data_dir = str(tmp_path)
            with pytest.raises(ValueError, match="too large"):
                save_upload("client1", "big.pdf", b"x" * (50 * 1024 * 1024 + 1))


# ---------------------------------------------------------------------------
# save_upload — TXT path (AC-1, AC-2, AC-3)
# ---------------------------------------------------------------------------


class TestSaveUploadTXT:
    def test_valid_txt_is_saved_with_txt_extension(self, tmp_path: Path):
        """AC-1: valid UTF-8 .txt file is stored with .txt extension."""
        with patch("neolex.services.document_manager.settings") as mock_settings:
            mock_settings.data_dir = str(tmp_path)
            meta = save_upload("client1", "statute.txt", _TXT_STUB)

        assert meta["filename"].endswith(".txt")
        assert meta["file_type"] == "txt"
        assert meta["size_bytes"] == len(_TXT_STUB)
        assert Path(meta["path"]).exists()
        assert Path(meta["path"]).read_bytes() == _TXT_STUB

    def test_binary_content_as_txt_raises(self, tmp_path: Path):
        """AC-2: binary content with .txt extension is rejected."""
        with patch("neolex.services.document_manager.settings") as mock_settings:
            mock_settings.data_dir = str(tmp_path)
            with pytest.raises(ValueError, match="null bytes|UTF-8"):
                save_upload("client1", "malicious.txt", _BINARY_STUB)

    def test_invalid_utf8_txt_raises(self, tmp_path: Path):
        """AC-2: non-UTF-8 bytes with .txt extension are rejected."""
        with patch("neolex.services.document_manager.settings") as mock_settings:
            mock_settings.data_dir = str(tmp_path)
            with pytest.raises(ValueError, match="null bytes|UTF-8"):
                save_upload("client1", "bad_encoding.txt", b"\xff\xfe not valid utf-8")

    def test_oversized_txt_raises(self, tmp_path: Path):
        """AC-3: oversized .txt file is rejected."""
        with patch("neolex.services.document_manager.settings") as mock_settings:
            mock_settings.data_dir = str(tmp_path)
            with pytest.raises(ValueError, match="too large"):
                save_upload("client1", "big.txt", b"a" * (50 * 1024 * 1024 + 1))

    def test_safe_filename_stem_preserved(self, tmp_path: Path):
        """Filename stem is sanitized but extension stays .txt."""
        with patch("neolex.services.document_manager.settings") as mock_settings:
            mock_settings.data_dir = str(tmp_path)
            meta = save_upload("client1", "zákon č. 89.txt", _TXT_STUB)

        assert meta["filename"].endswith(".txt")
        assert not meta["filename"].endswith(".pdf")


# ---------------------------------------------------------------------------
# extract_zip_safely — TXT support (AC-4, AC-5)
# ---------------------------------------------------------------------------


def _make_zip(*entries: tuple[str, bytes]) -> bytes:
    """Build an in-memory ZIP with the given (name, content) entries."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in entries:
            zf.writestr(name, content)
    return buf.getvalue()


class TestExtractZipSafelyTXT:
    def test_zip_with_only_txt_files_imports_all(self):
        """AC-4: ZIP containing only .txt files extracts all valid ones."""
        zb = _make_zip(
            ("doc1.txt", _TXT_STUB),
            ("doc2.txt", b"Second legal document.\n"),
        )
        valid, skipped = extract_zip_safely(zb)
        assert len(valid) == 2
        assert len(skipped) == 0
        names = {name for name, _ in valid}
        assert names == {"doc1.txt", "doc2.txt"}

    def test_zip_with_mixed_pdf_and_txt_imports_both(self):
        """AC-5: ZIP with both PDF and TXT imports both; other types are skipped."""
        zb = _make_zip(
            ("contract.pdf", _PDF_STUB),
            ("notes.txt", _TXT_STUB),
            ("readme.md", b"# Readme"),  # should be skipped
        )
        valid, skipped = extract_zip_safely(zb)
        names = {name for name, _ in valid}
        assert "contract.pdf" in names
        assert "notes.txt" in names
        assert len(skipped) == 1
        assert skipped[0][0] == "readme.md"
        assert skipped[0][1] == "skipped_not_pdf"

    def test_binary_txt_in_zip_is_skipped_as_invalid(self):
        """Binary content with .txt extension inside ZIP is skipped (not raised)."""
        zb = _make_zip(("evil.txt", _BINARY_STUB))
        valid, skipped = extract_zip_safely(zb)
        assert len(valid) == 0
        assert skipped[0] == ("evil.txt", "skipped_invalid")

    def test_zip_with_invalid_pdf_is_skipped(self):
        """PDF entry without %PDF magic bytes is skipped as invalid."""
        zb = _make_zip(("fake.pdf", b"This is not a PDF"))
        valid, skipped = extract_zip_safely(zb)
        assert len(valid) == 0
        assert skipped[0][1] == "skipped_invalid"

    def test_empty_txt_in_zip_is_skipped(self):
        """Empty .txt entry in ZIP is skipped as empty."""
        zb = _make_zip(("empty.txt", b""))
        valid, skipped = extract_zip_safely(zb)
        assert len(valid) == 0
        assert skipped[0][1] == "skipped_empty"
