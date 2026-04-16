"""Document management service — upload, list, delete, per-client storage.

Per-client isolation: each client's files live under:
    data/clients/<client_slug>/docs/<doc_id>_<filename>

This module is synchronous (uses pathlib/os) and is called from async
route handlers via asyncio.to_thread() where I/O matters.
"""

from __future__ import annotations

import datetime
import os
import re
import stat
import uuid
import zipfile
from pathlib import Path

from neolex.config import settings

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB (DOC-02)
PDF_MAGIC = b"%PDF"  # First 4 bytes of every valid PDF file

# ZIP upload limits
MAX_ZIP_BYTES = 200 * 1024 * 1024  # 200 MB max ZIP file size
MAX_ZIP_FILES = 100  # Max files in a ZIP
MAX_ZIP_EXTRACTED_BYTES = 500 * 1024 * 1024  # 500 MB max total extracted
MAX_COMPRESSION_RATIO = 100  # Max compression ratio per file


# ---------------------------------------------------------------------------
# Content validation helpers
# ---------------------------------------------------------------------------


# Encoding fallback chain — matches the indexer's _TXT_ENCODINGS so uploaded files
# that the indexer can read are never rejected by the upload validator.
_TEXT_ENCODINGS = ("utf-8", "cp1250", "iso-8859-2")


def _is_valid_text_content(data: bytes) -> bool:
    """Return True if *data* looks like text rather than binary content.

    Accepts UTF-8, cp1250, and iso-8859-2 encoded files — the same set the
    indexer tries — so Czech legal documents in legacy encodings are not
    incorrectly rejected at upload time.

    Rejects files that:
    - Contain null bytes (reliable binary/executable marker)
    - Cannot be decoded by any of the supported encodings (strict mode)
    """
    if b"\x00" in data:
        return False
    for enc in _TEXT_ENCODINGS:
        try:
            data.decode(enc)
            return True
        except UnicodeDecodeError:
            continue
    return False


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------


def client_docs_dir(client_slug: str) -> Path:
    """Return the docs directory for a client, creating it if needed."""
    path = Path(settings.data_dir) / "clients" / client_slug / "docs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def client_index_dir(client_slug: str) -> Path:
    """Return the index directory for a client, creating it if needed."""
    path = Path(settings.data_dir) / "clients" / client_slug / "index"
    path.mkdir(parents=True, exist_ok=True)
    return path


# ---------------------------------------------------------------------------
# Core operations
# ---------------------------------------------------------------------------


def save_upload(
    client_slug: str,
    filename: str,
    content: bytes,
    collection: str = "My Documents",
) -> dict:
    """Save uploaded PDF or TXT bytes to the client's docs directory.

    File type is determined by the filename extension (.txt → text, anything else → PDF).
    Returns document metadata dict (matches DocumentMeta schema).
    Raises ValueError for invalid file type or size.
    """
    # Validate size
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError(f"File too large: {len(content)} bytes (max {MAX_UPLOAD_BYTES})")

    # Determine file type and validate content accordingly
    file_ext = Path(filename).suffix.lower()
    if file_ext == ".txt":
        file_type = "txt"
        if not _is_valid_text_content(content):
            raise ValueError(
                "Not a valid text file — file contains null bytes or cannot be decoded as UTF-8, cp1250, or iso-8859-2"
            )
    else:
        # Treat as PDF for any other extension (including no extension)
        file_type = "pdf"
        if not content.startswith(PDF_MAGIC):
            raise ValueError("Not a valid PDF — file must start with %PDF")

    doc_id = str(uuid.uuid4())
    upload_ts = datetime.datetime.utcnow().isoformat()

    docs_dir = client_docs_dir(client_slug)
    # Sanitize: strip path components, restrict to safe chars, preserve real extension.
    stem = re.sub(r"[^a-zA-Z0-9._\- ]", "_", Path(filename).stem)[:180].strip("._- ") or "document"
    safe_ext = ".txt" if file_type == "txt" else ".pdf"
    safe_filename = f"{stem}{safe_ext}"
    dest = docs_dir / f"{doc_id}_{safe_filename}"
    dest.write_bytes(content)

    return {
        "doc_id": doc_id,
        "filename": safe_filename,
        "size_bytes": len(content),
        "upload_ts": upload_ts,
        "indexed": False,
        "client_slug": client_slug,
        "path": str(dest),
        "collection": collection,
        "file_type": file_type,
    }


def list_documents(client_slug: str) -> list[dict]:
    """Return metadata for all documents uploaded by a client.

    Reads metadata from the sidecar .meta files written alongside each doc.
    Falls back to filesystem attributes if sidecar is missing.
    """
    docs_dir = client_docs_dir(client_slug)
    results = []

    for meta_file in sorted(docs_dir.glob("*.meta")):
        import json

        try:
            data = json.loads(meta_file.read_text())
            results.append(data)
        except Exception:
            pass  # Skip corrupt meta files

    return results


def get_collection_names(client_slug: str) -> set[str]:
    """Return the set of distinct collection names for a client's corpus.

    Reads collection names from .meta sidecar files.  Corrupt or missing files
    are silently skipped.  Falls back to the default collection name so that
    documents without a sidecar are counted as occupying one collection slot.
    """
    import json

    docs_dir = client_docs_dir(client_slug)
    collections: set[str] = set()
    for meta_path in docs_dir.glob("*.meta"):
        try:
            meta = json.loads(meta_path.read_text())
            collections.add(meta.get("collection", "My Documents"))
        except Exception:
            pass
    return collections


def save_doc_meta(client_slug: str, meta: dict) -> None:
    """Write document metadata to a sidecar .meta file."""
    import json

    docs_dir = client_docs_dir(client_slug)
    meta_path = docs_dir / f"{meta['doc_id']}.meta"
    meta_path.write_text(json.dumps(meta, indent=2))


def mark_indexed(client_slug: str, doc_id: str) -> None:
    """Update the sidecar .meta to set indexed=True."""
    import json

    docs_dir = client_docs_dir(client_slug)
    meta_path = docs_dir / f"{doc_id}.meta"
    if meta_path.exists():
        data = json.loads(meta_path.read_text())
        data["indexed"] = True
        meta_path.write_text(json.dumps(data, indent=2))


def delete_document(client_slug: str, doc_id: str) -> bool:
    """Delete a document file and its sidecar. Returns True if deleted, False if not found."""
    docs_dir = client_docs_dir(client_slug)

    # Find the actual doc file (named <doc_id>_<filename>)
    deleted = False
    for f in docs_dir.glob(f"{doc_id}_*"):
        f.unlink(missing_ok=True)
        deleted = True

    # Remove sidecar
    meta_path = docs_dir / f"{doc_id}.meta"
    if meta_path.exists():
        meta_path.unlink()
        deleted = True

    return deleted


def get_document_path(client_slug: str, doc_id: str) -> Path | None:
    """Return the Path of the stored PDF, or None if not found."""
    docs_dir = client_docs_dir(client_slug)
    matches = list(docs_dir.glob(f"{doc_id}_*"))
    return matches[0] if matches else None


# ---------------------------------------------------------------------------
# ZIP extraction
# ---------------------------------------------------------------------------


def extract_zip_safely(
    zip_bytes: bytes,
    max_files: int = MAX_ZIP_FILES,
    max_total_bytes: int = MAX_ZIP_EXTRACTED_BYTES,
) -> tuple[list[tuple[str, bytes]], list[tuple[str, str]]]:
    """Extract PDFs and TXT files from a ZIP archive with comprehensive security checks.

    Returns ``(valid_files, skipped_files)`` where:
    - *valid_files*: list of ``(filename, file_bytes)`` tuples for accepted PDF/TXT entries
    - *skipped_files*: list of ``(filename, reason)`` tuples

    Raises :class:`ValueError` for zip bombs, path traversal, encrypted
    archives, or archives exceeding *max_files*.
    """
    import io

    if not zipfile.is_zipfile(io.BytesIO(zip_bytes)):
        raise ValueError("Uploaded file is not a valid ZIP archive.")

    valid_files: list[tuple[str, bytes]] = []
    skipped_files: list[tuple[str, str]] = []

    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        entries = zf.infolist()

        # --- Max file count ---
        if len(entries) > max_files:
            raise ValueError(f"ZIP contains {len(entries)} entries (max {max_files}). Split into smaller archives.")

        total_extracted = 0

        for info in entries:
            name = info.filename

            # --- Directory entries ---
            if name.endswith("/"):
                continue

            # --- macOS archive artifacts (silently skip, don't surface to user) ---
            if name.startswith("__MACOSX/") or os.path.basename(name) in (".DS_Store", "Thumbs.db"):
                continue
            if os.path.basename(name).startswith("._"):
                continue

            # --- Path traversal ---
            if ".." in name or name.startswith("/"):
                raise ValueError(
                    f"Unsafe path detected in ZIP entry: '{name}'. Archive may contain a path traversal attack.",
                )

            # --- Symlinks (Unix external_attr: upper 16 bits contain mode) ---
            unix_mode = (info.external_attr >> 16) & 0xFFFF
            if unix_mode and stat.S_ISLNK(unix_mode):
                skipped_files.append((os.path.basename(name), "skipped_symlink"))
                continue

            # --- Nested ZIPs ---
            basename = os.path.basename(name)
            if basename.lower().endswith(".zip"):
                skipped_files.append((basename, "skipped_nested_zip"))
                continue

            # --- Compression ratio check (pre-extraction) ---
            if info.compress_size > 0:
                ratio = info.file_size / info.compress_size
                if ratio > MAX_COMPRESSION_RATIO:
                    raise ValueError(
                        f"Suspicious compression ratio ({ratio:.0f}:1) for '{basename}'. Possible zip bomb.",
                    )

            # --- Total extracted size guard (pre-extraction estimate) ---
            if total_extracted + info.file_size > max_total_bytes:
                raise ValueError(
                    f"Total extracted size would exceed {max_total_bytes // (1024 * 1024)} MB. "
                    f"Possible zip bomb or archive too large.",
                )

            # --- Extract bytes ---
            try:
                data = zf.read(info)
            except RuntimeError as exc:
                # Encrypted / password-protected entry
                if "password" in str(exc).lower() or "encrypted" in str(exc).lower():
                    raise ValueError(
                        "ZIP archive contains encrypted entries. Password-protected archives are not supported.",
                    ) from exc
                raise

            # --- Post-extraction size verification ---
            total_extracted += len(data)
            if total_extracted > max_total_bytes:
                raise ValueError(
                    f"Total extracted size exceeds {max_total_bytes // (1024 * 1024)} MB. "
                    f"Possible zip bomb or archive too large.",
                )

            # --- Accept only PDF and TXT ---
            lname = basename.lower()
            is_pdf = lname.endswith(".pdf")
            is_txt = lname.endswith(".txt")
            if not is_pdf and not is_txt:
                skipped_files.append((basename, "skipped_unsupported_format"))
                continue

            # --- Empty files ---
            if len(data) == 0:
                skipped_files.append((basename, "skipped_empty"))
                continue

            # --- Content validation per file type ---
            if is_pdf and not data.startswith(PDF_MAGIC):
                skipped_files.append((basename, "skipped_invalid"))
                continue

            if is_txt and not _is_valid_text_content(data):
                skipped_files.append((basename, "skipped_invalid"))
                continue

            # --- Individual file size limit ---
            if len(data) > MAX_UPLOAD_BYTES:
                skipped_files.append((basename, "skipped_too_large"))
                continue

            valid_files.append((basename, data))

    return valid_files, skipped_files
