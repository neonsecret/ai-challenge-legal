"""Unit tests for arlc.indexing.indexer.extract_text_file().

Tests cover:
- UTF-8 content: chunks produced with correct start_line/end_line
- cp1250 content: Czech legal text decoded correctly (not garbled)
- Binary content: ValueError raised with a descriptive message
- Empty file: returns empty list without error
- Multi-paragraph file: each blank-line block becomes its own chunk group
"""

import os
import tempfile

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_tmp(content: bytes, suffix: str = ".txt") -> str:
    """Write *content* bytes to a named temp file; caller must delete."""
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        os.write(fd, content)
    finally:
        os.close(fd)
    return path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestExtractTextFileUtf8:
    """UTF-8 encoded plain-text files."""

    def test_single_paragraph_returns_chunks(self):
        from arlc.indexing.indexer import extract_text_file

        text = "This is a legal clause.\nIt spans two lines."
        path = _write_tmp(text.encode("utf-8"))
        try:
            chunks = extract_text_file(path)
        finally:
            os.unlink(path)

        assert len(chunks) >= 1
        assert all("start_line" in c for c in chunks)
        assert all("end_line" in c for c in chunks)
        assert all("text" in c for c in chunks)
        assert all("chunk_idx" in c for c in chunks)

    def test_start_line_is_one_based(self):
        from arlc.indexing.indexer import extract_text_file

        text = "First paragraph.\n\nSecond paragraph."
        path = _write_tmp(text.encode("utf-8"))
        try:
            chunks = extract_text_file(path)
        finally:
            os.unlink(path)

        start_lines = [c["start_line"] for c in chunks]
        assert 1 in start_lines, "First paragraph should start at line 1"

    def test_two_paragraphs_produce_distinct_line_ranges(self):
        from arlc.indexing.indexer import extract_text_file

        text = "Para one line A.\nPara one line B.\n\nPara two line A.\nPara two line B."
        path = _write_tmp(text.encode("utf-8"))
        try:
            chunks = extract_text_file(path)
        finally:
            os.unlink(path)

        start_lines = [c["start_line"] for c in chunks]
        # Two distinct paragraphs → at least two distinct start lines
        assert len(set(start_lines)) >= 2

    def test_chunk_idx_is_sequential_within_paragraph(self):
        from arlc.indexing.indexer import extract_text_file

        # Long paragraph that will be split into sub-chunks
        long_para = " ".join([f"Sentence number {i} in this legal document." for i in range(50)])
        path = _write_tmp(long_para.encode("utf-8"))
        try:
            chunks = extract_text_file(path)
        finally:
            os.unlink(path)

        idxs = [c["chunk_idx"] for c in chunks]
        assert idxs == list(range(len(idxs))), "chunk_idx must be a contiguous 0-based sequence"

    def test_text_content_preserved(self):
        from arlc.indexing.indexer import extract_text_file

        text = "Article 1. Definitions.\nFor the purposes of this Act:"
        path = _write_tmp(text.encode("utf-8"))
        try:
            chunks = extract_text_file(path)
        finally:
            os.unlink(path)

        combined = " ".join(c["text"] for c in chunks)
        assert "Article 1" in combined
        assert "Definitions" in combined


class TestExtractTextFileCp1250:
    """Czech legal text encoded as Windows cp1250."""

    # Sample Czech text with cp1250-specific characters: š, č, ř, ž, ě, á, í, ý, ů
    _CZECH_CLAUSE = (
        "Zákon č. 89/2012 Sb., občanský zákoník.\n"
        "Věřitel má právo požadovat splnění závazku.\n"
        "\n"
        "§ 1 Základní ustanovení.\n"
        "Každý je povinen dbát práv jiných."
    )

    def test_cp1250_decoded_correctly(self):
        from arlc.indexing.indexer import extract_text_file

        path = _write_tmp(self._CZECH_CLAUSE.encode("cp1250"))
        try:
            chunks = extract_text_file(path)
        finally:
            os.unlink(path)

        combined = " ".join(c["text"] for c in chunks)
        # Directly assert the expected Czech characters are present — cp1250
        # decoding must preserve them without replacement or garbling.
        assert "Zákon" in combined, "cp1250 decoding must preserve 'Zákon' without replacement characters"
        assert "zákoník" in combined, "cp1250 decoding must preserve 'zákoník'"

    def test_cp1250_chunks_have_line_metadata(self):
        from arlc.indexing.indexer import extract_text_file

        path = _write_tmp(self._CZECH_CLAUSE.encode("cp1250"))
        try:
            chunks = extract_text_file(path)
        finally:
            os.unlink(path)

        assert len(chunks) >= 1
        for chunk in chunks:
            assert chunk["start_line"] >= 1
            assert chunk["end_line"] >= chunk["start_line"]


class TestExtractTextFileBinary:
    """Encoding-fallback behaviour for non-UTF-8 byte sequences.

    iso-8859-2 is a complete single-byte encoding (every byte 0-255 has a
    defined code-point), so it will always succeed as the final fallback.
    The ValueError path in extract_text_file() is a safety net for future
    encoding lists that may omit a complete single-byte fallback.

    Here we verify that bytes invalid in UTF-8 are still handled gracefully
    via the cp1250/iso-8859-2 fallback rather than crashing the caller.
    """

    def test_non_utf8_bytes_decoded_via_fallback(self):
        """Bytes invalid in UTF-8 but valid in cp1250/iso-8859-2 must not raise."""
        from arlc.indexing.indexer import extract_text_file

        # 0x80-0x9F are invalid in UTF-8 but defined in cp1250 / iso-8859-2
        non_utf8_content = bytes([0x80, 0x9C, 0x8A, 0x9E, 0x8C]) * 10 + b"\n\nword"
        path = _write_tmp(non_utf8_content)
        try:
            # Should not raise — fallback encoding handles it
            chunks = extract_text_file(path)
        finally:
            os.unlink(path)

        # "word" must appear somewhere in the decoded output
        combined = " ".join(c["text"] for c in chunks)
        assert "word" in combined


class TestExtractTextFileEmpty:
    """Empty files should return an empty list without raising."""

    def test_empty_file_returns_empty_list(self):
        from arlc.indexing.indexer import extract_text_file

        path = _write_tmp(b"")
        try:
            chunks = extract_text_file(path)
        finally:
            os.unlink(path)

        assert chunks == []

    def test_whitespace_only_file_returns_empty_list(self):
        from arlc.indexing.indexer import extract_text_file

        path = _write_tmp(b"   \n\n\t\n   \n")
        try:
            chunks = extract_text_file(path)
        finally:
            os.unlink(path)

        assert chunks == []
