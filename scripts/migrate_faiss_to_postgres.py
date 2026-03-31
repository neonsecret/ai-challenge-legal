"""Migrate FAISS indexes + JSON metadata → PostgreSQL pgvector chunks table.

Reads FAISS .bin files (embeddings) and .json sidecar files (metadata),
batch-inserts into the chunks table.  Run via:

    uv run python scripts/migrate_faiss_to_postgres.py
"""
from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

import faiss
import numpy as np
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from pgvector.psycopg2 import register_vector

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# Convert async DSN to sync: postgresql+asyncpg:// → postgresql://
_dsn = os.environ["DATABASE_URL"]
SYNC_DSN = _dsn.replace("postgresql+asyncpg://", "postgresql://")

BATCH_SIZE = 500

# Corpus definitions: (faiss_bin, metadata_json, corpus_name, tenant_id)
CORPORA: list[tuple[Path, Path, str, str | None]] = [
    (
        PROJECT_ROOT / "data" / "faiss_llama-server.bin",
        PROJECT_ROOT / "data" / "faiss_llama-server.json",
        "difc",
        None,
    ),
    (
        PROJECT_ROOT / "data" / "faiss_czech.bin",
        PROJECT_ROOT / "data" / "faiss_czech.json",
        "czech",
        None,
    ),
]

# Discover custom tenant corpora under data/clients/{uuid}/index/
CLIENTS_DIR = PROJECT_ROOT / "data" / "clients"
if CLIENTS_DIR.exists():
    for client_dir in sorted(CLIENTS_DIR.iterdir()):
        if not client_dir.is_dir():
            continue
        idx_dir = client_dir / "index"
        faiss_bin = idx_dir / "faiss_index.bin"
        faiss_json = idx_dir / "faiss_metadata.json"
        if faiss_bin.exists() and faiss_json.exists():
            # Directory name IS the tenant UUID (or a slug for dev data)
            tenant_name = client_dir.name
            try:
                tenant_uuid = str(uuid.UUID(tenant_name))
            except ValueError:
                # Non-UUID directory names (e.g. "test-co") — skip
                print(f"  Skipping non-UUID client dir: {tenant_name}")
                continue
            CORPORA.append((faiss_bin, faiss_json, tenant_uuid, tenant_uuid))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_row(
    meta: dict,
    embedding: np.ndarray,
    corpus: str,
    tenant_id: str | None,
) -> tuple:
    """Build a row tuple for batch INSERT."""
    row_id = str(uuid.uuid4())
    chunk_id = meta["chunk_id"]
    # Custom corpora lack doc_id — fall back to pdf_id
    doc_id = meta.get("doc_id", meta.get("pdf_id", ""))
    pdf_id = meta.get("pdf_id", "")
    page = int(meta.get("page", 0))
    source_file = meta.get("source_file", "")
    text = meta.get("text", "")

    # Corpus-specific fields go into metadata_extra
    extra: dict = {}
    for key in ("entities", "doc_type", "court_division"):
        if key in meta and meta[key]:
            extra[key] = meta[key]
    metadata_extra = json.dumps(extra) if extra else None

    return (
        row_id,
        corpus,
        tenant_id,
        doc_id,
        pdf_id,
        page,
        chunk_id,
        source_file,
        text,
        embedding.tolist(),
        metadata_extra,
    )


def migrate_corpus(
    conn,
    faiss_path: Path,
    meta_path: Path,
    corpus: str,
    tenant_id: str | None,
) -> int:
    """Migrate a single corpus, returns number of rows inserted."""
    print(f"\n{'='*60}")
    print(f"Corpus: {corpus}")
    print(f"  FAISS: {faiss_path}")
    print(f"  Meta:  {meta_path}")

    # Load FAISS index
    index = faiss.read_index(str(faiss_path))
    n_vectors = index.ntotal
    dim = index.d
    print(f"  Vectors: {n_vectors}  dim: {dim}")

    # Skip corpora with wrong dimensions (e.g. old Snowflake 1024-dim)
    if dim != 4096:
        print(f"  SKIP: dimension {dim} != 4096 (needs re-indexing with Qwen3-8B)")
        return 0

    # Load metadata
    with open(meta_path) as f:
        metadata = json.load(f)
    print(f"  Metadata entries: {len(metadata)}")

    if len(metadata) != n_vectors:
        print(f"  WARNING: metadata ({len(metadata)}) != vectors ({n_vectors})")
        # Use the smaller count
        n = min(len(metadata), n_vectors)
    else:
        n = n_vectors

    # Batch insert
    cur = conn.cursor()
    inserted = 0
    batch: list[tuple] = []

    for i in range(n):
        embedding = index.reconstruct(i)
        row = _build_row(metadata[i], embedding, corpus, tenant_id)
        batch.append(row)

        if len(batch) >= BATCH_SIZE:
            _insert_batch(cur, batch)
            inserted += len(batch)
            print(f"  Inserted {inserted}/{n} chunks", end="\r")
            batch = []

    # Final partial batch
    if batch:
        _insert_batch(cur, batch)
        inserted += len(batch)

    conn.commit()
    print(f"  Inserted {inserted}/{n} chunks — done.")
    return inserted


def _insert_batch(cur, batch: list[tuple]) -> None:
    """Execute batch INSERT with ON CONFLICT skip for idempotent reruns."""
    psycopg2.extras.execute_values(
        cur,
        """
        INSERT INTO chunks (
            id, corpus, tenant_id, doc_id, pdf_id, page,
            chunk_id, source_file, text, embedding, metadata_extra
        ) VALUES %s
        ON CONFLICT (chunk_id) DO NOTHING
        """,
        batch,
        template=(
            "(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::vector, %s::jsonb)"
        ),
        page_size=BATCH_SIZE,
    )


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def verify(conn) -> None:
    """Run verification queries after migration."""
    cur = conn.cursor()

    print(f"\n{'='*60}")
    print("VERIFICATION")
    print(f"{'='*60}")

    # Count by corpus
    cur.execute("SELECT corpus, count(*) FROM chunks GROUP BY corpus ORDER BY corpus")
    rows = cur.fetchall()
    print("\nChunks per corpus:")
    total = 0
    for corpus, count in rows:
        print(f"  {corpus}: {count}")
        total += count
    print(f"  TOTAL: {total}")

    # Null embeddings
    cur.execute("SELECT count(*) FROM chunks WHERE embedding IS NULL")
    null_emb = cur.fetchone()[0]
    print(f"\nNull embeddings: {null_emb}")

    # Null tsvector (trigger should have populated these)
    cur.execute("SELECT count(*) FROM chunks WHERE text_search IS NULL")
    null_ts = cur.fetchone()[0]
    print(f"Null text_search: {null_ts}")

    # Vector similarity test (inner product)
    print("\nVector similarity test (top 5 nearest to first DIFC chunk):")
    cur.execute("""
        SELECT chunk_id,
               embedding <#> (SELECT embedding FROM chunks
                              WHERE chunk_id = 'arbitration_law_difc_law_no_1_of_2008_1_0') AS score
        FROM chunks
        WHERE corpus = 'difc'
        ORDER BY embedding <#> (SELECT embedding FROM chunks
                                WHERE chunk_id = 'arbitration_law_difc_law_no_1_of_2008_1_0')
        LIMIT 5
    """)
    for cid, score in cur.fetchall():
        print(f"  {cid}: {score:.6f}")

    # Full-text search test
    print("\nFull-text search test ('arbitration law' in DIFC):")
    cur.execute("""
        SELECT chunk_id,
               ts_rank(text_search, plainto_tsquery('simple', 'arbitration law')) AS rank
        FROM chunks
        WHERE corpus = 'difc'
          AND text_search @@ plainto_tsquery('simple', 'arbitration law')
        ORDER BY rank DESC
        LIMIT 5
    """)
    for cid, rank in cur.fetchall():
        print(f"  {cid}: {rank:.6f}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("Connecting to PostgreSQL...")
    conn = psycopg2.connect(SYNC_DSN)
    register_vector(conn)

    # Ensure pgvector extension exists
    cur = conn.cursor()
    cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
    conn.commit()

    total_inserted = 0
    for faiss_path, meta_path, corpus, tenant_id in CORPORA:
        if not faiss_path.exists():
            print(f"\n  SKIP: {faiss_path} not found")
            continue
        if not meta_path.exists():
            print(f"\n  SKIP: {meta_path} not found")
            continue
        count = migrate_corpus(conn, faiss_path, meta_path, corpus, tenant_id)
        total_inserted += count

    print(f"\n\nTotal chunks inserted: {total_inserted}")

    verify(conn)
    conn.close()
    print("\nMigration complete.")


if __name__ == "__main__":
    main()
