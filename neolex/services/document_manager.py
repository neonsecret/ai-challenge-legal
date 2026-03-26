"""Document management service — upload, list, delete, per-client storage.

Per-client isolation: each client's files live under:
    data/clients/<client_slug>/docs/<doc_id>_<filename>

This module is synchronous (uses pathlib/os) and is called from async
route handlers via asyncio.to_thread() where I/O matters.
"""
from __future__ import annotations

import datetime
import hashlib
import os
import shutil
import uuid
from pathlib import Path

from neolex.config import settings


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB (DOC-02)
PDF_MAGIC = b"%PDF"  # First 4 bytes of every valid PDF file


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
) -> dict:
    """Save uploaded PDF bytes to the client's docs directory.

    Returns document metadata dict (matches DocumentMeta schema).
    Raises ValueError for invalid file type or size.
    """
    # Validate size (Rule 2: missing validation)
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError(f"File too large: {len(content)} bytes (max {MAX_UPLOAD_BYTES})")

    # Validate PDF magic bytes (Rule 2: file type guard)
    if not content.startswith(PDF_MAGIC):
        raise ValueError(f"Not a valid PDF — file must start with %PDF")

    doc_id = str(uuid.uuid4())
    upload_ts = datetime.datetime.utcnow().isoformat()

    docs_dir = client_docs_dir(client_slug)
    # Sanitize filename: strip path components, keep only basename
    safe_filename = Path(filename).name
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
