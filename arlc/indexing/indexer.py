"""Index PDF documents into PostgreSQL (pgvector) for retrieval."""

import base64
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import pymupdf
from dotenv import load_dotenv

load_dotenv()

from arlc.llm.router import call_llm

# ---------------------------------------------------------------------------
# Entity extraction at index time
# Inspired by CPBD (Azamat Yelmagambetov, 1st place) who indexes entities as
# a separate BM25 column alongside raw text. We extract entities from each
# chunk at index time and store them as a metadata field so retrievers can
# use entity-aware filtering without re-parsing at query time.
# ---------------------------------------------------------------------------

# Load case metadata for party name entity extraction
_CASE_METADATA_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "case_metadata_index.json")
_case_metadata: dict = {}


def _load_case_metadata() -> dict:
    global _case_metadata
    if _case_metadata:
        return _case_metadata
    if os.path.exists(_CASE_METADATA_PATH):
        try:
            with open(_CASE_METADATA_PATH) as f:
                _case_metadata = json.load(f)
        except Exception:
            pass
    return _case_metadata


# Regex patterns for entity extraction from chunk text
_ENTITY_PATTERNS = [
    # Case numbers: SCT 295/2025, CFI 010/2024, ENF-022-2023, etc.
    re.compile(r"\b((?:CFI|CA|ARB|ENF|SCT|TCD|DEC)[\s\-_]*\d+[\s/\-_]*\d+)\b", re.IGNORECASE),
    # Article references: Article 14, Article 14(2)(b)
    re.compile(r"\b(Article\s+\d+(?:\(\w+\))*)\b", re.IGNORECASE),
    # Law number references: Law No. 5 of 2020, DIFC Law No. 2
    re.compile(r"\b((?:DIFC\s+)?Law\s+No\.?\s*\d+(?:\s+of\s+\d+)?)\b", re.IGNORECASE),
    # Regulation references: Regulation No. 1
    re.compile(r"\b(Regulation\s+No\.?\s*\d+)\b", re.IGNORECASE),
]


def extract_entities_from_chunk(text: str) -> list[str]:
    """Extract legal entities (case IDs, article refs, law names) from chunk text.

    Returns deduplicated list of entity strings, normalized to lowercase.
    Used at index time to populate the 'entities' metadata field.
    """
    entities: set[str] = set()
    for pattern in _ENTITY_PATTERNS:
        for match in pattern.findall(text):
            entity = re.sub(r"\s+", " ", match.strip()).lower()
            if entity:
                entities.add(entity)
    return sorted(entities)


DOCUMENTS_DIR = "data/documents"
# Embedding model: must match the retriever's model for consistent dimensions.
# Default: llama-server (Qwen3-8B via HTTP, 4096-dim).
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "llama-server")

_ocr_model = os.environ.get("MODEL_NAME", "")

_doc_summary_cache: dict[str, str] = {}

# Embedding decontamination insight from guy3 (structure-first methodology)
# Boilerplate patterns that dominate embedding space, making all pages of the
# same document cluster together instead of discriminating by content.
_BOILERPLATE_PATTERNS = [
    re.compile(r"IN\s+THE\s+DUBAI\s+INTERNATIONAL\s+FINANCIAL\s+CENTRE\s+COURTS?", re.IGNORECASE),
    re.compile(r"IN\s+THE\s+COURT\s+OF\s+FIRST\s+INSTANCE", re.IGNORECASE),
    re.compile(r"IN\s+THE\s+SMALL\s+CLAIMS\s+TRIBUNAL", re.IGNORECASE),
    re.compile(r"COURT\s+OF\s+APPEAL", re.IGNORECASE),
    re.compile(r"(?:Claim|Case)\s+No\s*:\s*\S+", re.IGNORECASE),
    re.compile(r"^BETWEEN\s*$", re.MULTILINE | re.IGNORECASE),
    re.compile(r"^(?:Claimant|Defendant|Respondent|Applicant)s?\s*$", re.MULTILINE | re.IGNORECASE),
    re.compile(r"Page\s+\d+\s+of\s+\d+", re.IGNORECASE),
    re.compile(r"^\s*\d{1,3}\s*$", re.MULTILINE),  # standalone page numbers
    re.compile(r"^\s*\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}\s*$", re.MULTILINE),  # date stamps on their own line
]


def clean_text_for_embedding(text: str, doc_metadata: dict | None = None) -> str:
    """Strip structural boilerplate from text before embedding.

    Removes repeated document titles, court headers, page numbers, and other
    structural elements that contaminate embedding space. The original text
    is preserved for BM25 and display — only the embedding vector uses this
    cleaned version.
    """
    cleaned = text

    # Strip document title if provided in metadata
    if doc_metadata and doc_metadata.get("title"):
        title = doc_metadata["title"]
        # Remove exact and near-exact title occurrences (case-insensitive)
        cleaned = re.sub(re.escape(title), "", cleaned, flags=re.IGNORECASE)

    # Strip known boilerplate patterns
    for pattern in _BOILERPLATE_PATTERNS:
        cleaned = pattern.sub("", cleaned)

    # Collapse excessive whitespace left by removals
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = cleaned.strip()

    return cleaned


# Legal structure header pattern for structure-aware chunking
_LEGAL_HEADER_PATTERN = re.compile(
    r"(?=\n(?:Article|Section|Part|Schedule|Appendix|Chapter)\s+[\dIVXivx]+)",
    re.IGNORECASE,
)


def _generate_doc_summary(pdf_id: str, first_pages_text: str) -> str:
    """Generate a short document-level summary for SAC."""
    if pdf_id in _doc_summary_cache:
        return _doc_summary_cache[pdf_id]

    prompt = f"""Read this legal document excerpt and write 1-2 sentences (max 200 characters) for a RETRIEVAL INDEX. Include:
- Document type: law / regulation / court case / enactment notice
- Key identifier: law name, law number, case number, year
- Main legal topic or subject matter
- Key article/section range if visible (e.g. "Arts. 1-15")

Text:
{first_pages_text[:2000]}

Output ONLY the retrieval index entry (max 200 chars), no preamble."""

    try:
        text, *_ = call_llm(
            system_prompt="You are a document summarizer.",
            user_message=prompt,
            max_tokens=80,
            model=os.environ.get("INDEXER_MODEL", "claude-sonnet-4-6"),
        )
        summary = text.strip()
        if len(summary) > 200:
            summary = summary[:197] + "..."
    except Exception as e:
        print(f"  Warning: SAC summary failed for {pdf_id[:16]}: {e}")
        summary = ""

    _doc_summary_cache[pdf_id] = summary
    return summary


_CHUNK_HEADER_PATTERN = re.compile(
    r"^((?:Article|Section|Part|Schedule|Appendix|Chapter)\s+[\dIVXivx]+[^.\n]{0,80})",
    re.IGNORECASE,
)


def _generate_chunk_context(pdf_id: str, doc_summary: str, chunk_text: str, chunk_key: str) -> str:
    """Generate chunk-specific retrieval context (Contextual Retrieval pattern).

    Fast path: extract legal structure header directly from chunk text (no LLM call).
    LLM fallback: only for chunks with no detectable legal header.
    """
    cache_key = f"{pdf_id}_{chunk_key}"
    if cache_key in _doc_summary_cache:
        return _doc_summary_cache[cache_key]

    # Fast path: extract article/section header from start of chunk (no LLM needed)
    header_match = _CHUNK_HEADER_PATTERN.match(chunk_text.strip())
    if header_match:
        context = header_match.group(1).strip()[:120]
        _doc_summary_cache[cache_key] = context
        return context

    # LLM fallback: only for unstructured chunks (court case narrative, preamble, etc.)
    prompt = f"""Document: {doc_summary}

Chunk text:
{chunk_text[:400]}

Write a 1-sentence (max 100 chars) context describing what this chunk covers. Include section/article number if visible.
Output ONLY the sentence."""

    try:
        text, *_ = call_llm(
            system_prompt="You are a document summarizer.",
            user_message=prompt,
            max_tokens=40,
            model=os.environ.get("INDEXER_MODEL", "claude-sonnet-4-6"),
        )
        context = text.strip()
        if len(context) > 120:
            context = context[:117] + "..."
    except Exception:
        context = ""

    _doc_summary_cache[cache_key] = context
    return context


def _ocr_page(page, pdf_file: str, page_num: int) -> str:
    """Use vision LLM to OCR a scanned PDF page."""
    if not _ocr_model:
        return ""
    try:
        # Render page to PNG image
        pix = page.get_pixmap(dpi=150)
        png_bytes = pix.tobytes("png")

        # Base64 encode
        img_b64 = base64.b64encode(png_bytes).decode()

        # Call vision API via LLM router
        # Note: call_llm doesn't support image blocks, so we use the anthropic SDK directly
        import anthropic as _anthropic_sdk

        _client = _anthropic_sdk.Anthropic()
        response = _client.messages.create(
            model=_ocr_model,
            max_tokens=2048,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": img_b64}},
                        {
                            "type": "text",
                            "text": "Extract all text from this legal document page. Return only the extracted text, no commentary.",
                        },
                    ],
                },
            ],
        )

        text = response.content[0].text.strip()
        print(f"  [OCR] {pdf_file} page {page_num + 1}")
        return text
    except Exception as e:
        print(f"  [OCR FAILED] {pdf_file} page {page_num + 1}: {e}")
        return ""


def split_page_into_chunks(text: str, page_num: int, max_chars: int = 500, overlap_chars: int = 0) -> list[dict]:
    """Split a page's text into paragraph-grouped chunks.

    Grounding stays page-accurate — all chunks get the source page number.
    Returns list of {"page": int, "text": str, "chunk_idx": int}.
    """
    # Short pages: don't split (no benefit, just overhead)
    if len(text) < 500:
        return [{"page": page_num, "text": text, "chunk_idx": 0}]

    # Try to split on legal structure boundaries first (article/section/part headers)
    header_splits = _LEGAL_HEADER_PATTERN.split(text)
    if len(header_splits) >= 2:
        # Use legal headers as chunk boundaries
        paragraphs = [s.strip() for s in header_splits if s.strip()]
    else:
        # Fallback: standard paragraph splitting
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]

    chunks = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) + 2 <= max_chars:
            current = (current + "\n\n" + para).strip() if current else para
        else:
            if current:
                chunks.append(current)
                current = ""

            # Check if paragraph itself exceeds max_chars — split at sentence boundaries
            if len(para) > max_chars:
                # Try sentence splitting first (on periods, question marks, exclamation marks)
                sentences = re.split(r"(?<=[.!?])\s+", para)

                # If no sentence boundaries found (e.g., legal lists with semicolons),
                # try splitting on semicolons or line breaks
                if len(sentences) == 1:
                    # Try semicolon splits for legal lists
                    sentences = [
                        s.strip() + ";" if i < len(para.split(";")) - 1 else s.strip()
                        for i, s in enumerate(para.split(";"))
                        if s.strip()
                    ]

                # If still one giant chunk, force split at max_chars
                if len(sentences) == 1 and len(sentences[0]) > max_chars:
                    # Hard split as last resort — use local var to avoid shadowing the param
                    _remaining = sentences[0]
                    while _remaining:
                        chunk_size = max_chars if len(_remaining) > max_chars else len(_remaining)
                        chunks.append(_remaining[:chunk_size])
                        _remaining = _remaining[chunk_size:]
                else:
                    # Process sentences/fragments normally
                    for sent in sentences:
                        if len(current) + len(sent) + 1 <= max_chars:
                            current = (current + " " + sent).strip() if current else sent
                        else:
                            if current:
                                chunks.append(current)
                            # If single sentence > max_chars, hard split it
                            if len(sent) > max_chars:
                                _remaining = sent
                                while _remaining:
                                    chunk_size = max_chars if len(_remaining) > max_chars else len(_remaining)
                                    chunks.append(_remaining[:chunk_size])
                                    _remaining = _remaining[chunk_size:]
                                current = ""
                            else:
                                current = sent
            else:
                # Paragraph fits within max_chars, start new chunk with it
                current = para if overlap_chars == 0 else current[-overlap_chars:].lstrip() + "\n\n" + para

    if current:
        chunks.append(current)

    if not chunks:
        return [{"page": page_num, "text": text, "chunk_idx": 0}]

    return [{"page": page_num, "text": c, "chunk_idx": i} for i, c in enumerate(chunks)]


def extract_pages(pdf_path: str) -> list[dict]:
    """Extract text from each page of a PDF, returning paragraph-level chunks.

    Returns list of dicts with keys: page (1-based), text, chunk_idx.
    """
    pdf_file = os.path.basename(pdf_path)
    doc = pymupdf.open(pdf_path)
    chunks = []
    for page_num in range(len(doc)):
        text = doc[page_num].get_text().strip()

        # If text is too short, try OCR (scanned page)
        if len(text) < 100:
            ocr_text = _ocr_page(doc[page_num], pdf_file, page_num)
            if ocr_text:
                text = ocr_text

        if text:
            page_chunks = split_page_into_chunks(text, page_num + 1)  # 1-based
            chunks.extend(page_chunks)

    doc.close()
    return chunks


# Candidate encodings for Czech legal text.  UTF-8 is tried first; cp1250 and
# iso-8859-2 cover legacy Windows and ISO-Latin-2 exports from Czech legal
# databases.
_TXT_ENCODINGS = ("utf-8", "cp1250", "iso-8859-2")


def extract_text_file(path: str) -> list[dict]:
    """Extract text chunks from a plain-text file with encoding fallback.

    Tries UTF-8 first, then cp1250, then falls back to iso-8859-2 with
    ``errors='replace'`` so the function always succeeds even for unrecognised
    byte sequences.  Never raises ``ValueError``.

    Splits the file into blank-line-delimited paragraphs and applies the same
    ``split_page_into_chunks`` logic used for PDFs, but tracks
    ``start_line`` / ``end_line`` (1-indexed) instead of ``page_num``.

    Returns list of dicts with keys: start_line (int), end_line (int), text
    (str), chunk_idx (int).  The caller is responsible for mapping start_line
    into the DB's ``page`` column.
    """
    with open(path, "rb") as fh:
        raw = fh.read()

    decoded: str | None = None
    used_encoding: str | None = None
    for enc in _TXT_ENCODINGS[:-1]:  # try strict decodings first
        try:
            decoded = raw.decode(enc)
            used_encoding = enc
            break
        except UnicodeDecodeError:
            continue

    if decoded is None:
        # Last-resort fallback: iso-8859-2 with replacement characters so we
        # never hard-fail on files with unexpected byte sequences.
        last_enc = _TXT_ENCODINGS[-1]
        decoded = raw.decode(last_enc, errors="replace")
        used_encoding = last_enc

    if used_encoding != "utf-8":
        print(f"  [txt] {os.path.basename(path)} decoded as {used_encoding}")

    lines = decoded.splitlines()

    # Build paragraph spans: (start_line_1based, end_line_1based, text)
    paragraphs: list[tuple[int, int, str]] = []
    para_lines: list[str] = []
    para_start = 1

    for i, line in enumerate(lines, start=1):
        if line.strip():
            if not para_lines:
                para_start = i
            para_lines.append(line)
        else:
            if para_lines:
                paragraphs.append((para_start, i - 1, "\n".join(para_lines)))
                para_lines = []

    if para_lines:
        paragraphs.append((para_start, len(lines), "\n".join(para_lines)))

    if not paragraphs:
        return []

    chunks: list[dict] = []
    global_chunk_idx = 0

    for start_line, end_line, para_text in paragraphs:
        # Re-use the same chunking logic as PDFs; pass start_line as the
        # surrogate page number so split_page_into_chunks works unchanged.
        sub_chunks = split_page_into_chunks(para_text, start_line)
        for sc in sub_chunks:
            chunks.append(
                {
                    "start_line": start_line,
                    "end_line": end_line,
                    "text": sc["text"],
                    "chunk_idx": global_chunk_idx,
                }
            )
            global_chunk_idx += 1

    return chunks


def _get_embedding_function():
    """Get the embedding function matching the retriever's backend.

    For llama-server (default): uses the retriever's LlamaServerEmbedder via HTTP.
    For SentenceTransformer models: loads locally with GPU auto-detection.
    """
    from arlc.retriever import _embedding_lock, get_embedding_model

    model = get_embedding_model()
    print("  Embedding via llama-server (same as retriever)")

    def encode(texts: list[str]) -> list[list[float]]:
        import numpy as np

        with _embedding_lock:
            embeddings = model.encode(texts, normalize_embeddings=True)
        return np.array(embeddings).tolist()

    return encode


def build_index(corpus: str = "difc", tenant_id: str | None = None):
    """Build vector index by inserting chunks into PostgreSQL (pgvector).

    Extracts pages from PDFs, splits into chunks, generates SAC context,
    computes embeddings, and INSERTs into the ``chunks`` table.

    Args:
        corpus: Corpus identifier ('difc', 'czech', or tenant UUID for custom).
        tenant_id: Tenant UUID for custom corpora, None for built-in.
    """
    ef = _get_embedding_function()

    all_doc_files = sorted(f for f in os.listdir(DOCUMENTS_DIR) if f.endswith(".pdf") or f.endswith(".txt"))
    print(f"Indexing {len(all_doc_files)} document(s) (model={EMBEDDING_MODEL}, corpus={corpus})...")

    all_ids: list[str] = []
    all_texts: list[str] = []
    all_metadatas: list[dict] = []
    # (idx, doc_id, summary, chunk_text, chunk_key) for concurrent context generation
    pending_contexts: list[tuple] = []

    for doc_file in all_doc_files:
        is_txt = doc_file.endswith(".txt")
        # Strip extension to get a stable doc identifier used for chunk IDs.
        doc_stem = doc_file[:-4] if is_txt else doc_file.replace(".pdf", "")
        doc_path = os.path.join(DOCUMENTS_DIR, doc_file)

        # For custom corpora, files are named {uuid}_{filename}.ext.
        # Read the .meta sidecar to get the canonical doc_id (pure UUID),
        # so doc_ids filtering matches what the frontend sends.
        canonical_doc_id = doc_stem
        meta_path = os.path.join(DOCUMENTS_DIR, doc_stem.split("_")[0] + ".meta")
        if os.path.exists(meta_path):
            try:
                with open(meta_path) as _mf:
                    _m = json.loads(_mf.read())
                if _m.get("doc_id"):
                    canonical_doc_id = _m["doc_id"]
            except Exception:
                pass

        # Dispatch extraction by file type.
        if is_txt:
            chunks = extract_text_file(doc_path)
            source_type = "txt"
        else:
            chunks = extract_pages(doc_path)
            source_type = "pdf"

        # SAC: generate per-document summary from the first ~3 pages / paragraphs.
        if is_txt:
            first_chunk_texts = [c["text"] for c in chunks[:3]]
        else:
            first_chunk_texts = [c["text"] for c in chunks if c["page"] <= 3]
        first_text = "\n\n".join(first_chunk_texts)
        summary = _generate_doc_summary(doc_stem, first_text) if first_text else ""
        if summary:
            print(f"  SAC summary for {doc_file}: {summary}")

        for chunk_info in chunks:
            if is_txt:
                # Use start_line as the positional key for chunk IDs (analogous to page).
                pos_key = chunk_info["start_line"]
                chunk_id = f"{doc_stem}_L{pos_key}_{chunk_info['chunk_idx']}"
                # page column stores start_line for TXT (DB column is NOT NULL).
                db_page = chunk_info["start_line"]
            else:
                pos_key = chunk_info["page"]
                chunk_id = f"{doc_stem}_{pos_key}_{chunk_info['chunk_idx']}"
                db_page = chunk_info["page"]

            all_ids.append(chunk_id)
            all_texts.append(chunk_info["text"])  # raw text; SAC prefix prepended below
            entities = extract_entities_from_chunk(chunk_info["text"])
            meta_entry: dict = {
                "pdf_id": doc_stem,
                "doc_id": canonical_doc_id,
                "page": db_page,
                "source_file": doc_file,
                "entities": "|".join(entities),
                "source_type": source_type,
            }
            if is_txt:
                meta_entry["start_line"] = chunk_info["start_line"]
                meta_entry["end_line"] = chunk_info["end_line"]
            all_metadatas.append(meta_entry)

            if summary:
                chunk_key = f"{pos_key}_{chunk_info['chunk_idx']}"
                pending_contexts.append((len(all_ids) - 1, doc_stem, summary, chunk_info["text"], chunk_key))

    # Generate per-chunk contexts concurrently.
    # Fast path (70%+ of chunks): rule-based header extraction — no LLM call.
    # LLM fallback: only for unstructured chunks (narrative text, preambles).
    if pending_contexts:
        print(f"  Generating chunk contexts for {len(pending_contexts)} chunks (concurrent)...")

        def _gen_context(args):
            idx, pdf_id, summary, chunk_text, chunk_key = args
            ctx = _generate_chunk_context(pdf_id, summary, chunk_text, chunk_key)
            return idx, summary, ctx

        max_workers = min(12, len(pending_contexts))
        completed = 0
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(_gen_context, args): args for args in pending_contexts}
            for future in as_completed(futures):
                idx, summary, context = future.result()
                safe_summary = summary.replace("]", "").replace("[", "")
                raw_text = all_texts[idx]
                if context:
                    safe_context = context.replace("]", "").replace("[", "")
                    all_texts[idx] = f"[DOCUMENT: {safe_summary} | {safe_context}]\n\n{raw_text}"
                else:
                    all_texts[idx] = f"[DOCUMENT: {safe_summary}]\n\n{raw_text}"
                completed += 1
                if completed % 200 == 0:
                    print(f"    {completed}/{len(pending_contexts)} contexts done")
        print(f"  Contexts complete ({len(pending_contexts)} chunks)")

    # Embedding decontamination: clean text for embedding, keep original for storage
    print("  Cleaning text for embedding decontamination...")
    all_embed_texts = []
    for i, text in enumerate(all_texts):
        meta = all_metadatas[i]
        doc_meta = {"title": meta.get("pdf_id", "").replace("_", " ")}
        all_embed_texts.append(clean_text_for_embedding(text, doc_meta))

    # Pre-compute embeddings from cleaned text
    print("  Computing embeddings from decontaminated text...")
    all_embeddings = ef(all_embed_texts)

    # --- Insert into PostgreSQL (pgvector) ---
    from sqlalchemy import create_engine
    from sqlalchemy import text as sa_text

    db_url = os.environ.get("DATABASE_URL", "")
    if "+asyncpg" in db_url:
        db_url = db_url.replace("+asyncpg", "")
    engine = create_engine(db_url)

    print(f"  Inserting {len(all_ids)} chunks into PostgreSQL (corpus={corpus})...")

    with engine.begin() as conn:
        # Delete existing chunks for this corpus (clean rebuild)
        conn.execute(
            sa_text("DELETE FROM chunks WHERE corpus = :corpus"),
            {"corpus": corpus},
        )

        # Batch insert with UPSERT as safety net
        for i in range(0, len(all_ids), 64):
            batch_end = min(i + 64, len(all_ids))
            for j in range(i, batch_end):
                chunk_id = all_ids[j]
                meta = all_metadatas[j]
                text = all_texts[j]
                emb = all_embeddings[j]

                vec_str = "[" + ",".join(str(float(x)) for x in emb) + "]"

                # Store entities, source_type, doc_type, court_division, and
                # TXT-specific line range in metadata_extra JSONB.
                extra: dict = {}
                entities_str = meta.get("entities", "")
                if entities_str:
                    extra["entities"] = entities_str
                # source_type distinguishes pdf vs txt chunks for citation rendering.
                extra["source_type"] = meta.get("source_type", "pdf")
                if meta.get("doc_type"):
                    extra["doc_type"] = meta["doc_type"]
                if meta.get("court_division"):
                    extra["court_division"] = meta["court_division"]
                # TXT line-range metadata for citation grounding.
                if meta.get("start_line") is not None:
                    extra["start_line"] = meta["start_line"]
                if meta.get("end_line") is not None:
                    extra["end_line"] = meta["end_line"]

                conn.execute(
                    sa_text("""
                        INSERT INTO chunks
                            (corpus, tenant_id, doc_id, pdf_id, page, chunk_id,
                             source_file, text, embedding, metadata_extra)
                        VALUES
                            (:corpus, :tenant_id, :doc_id, :pdf_id, :page, :chunk_id,
                             :source_file, :text, cast(:embedding as vector), :metadata_extra)
                        ON CONFLICT (chunk_id) DO UPDATE SET
                            text = EXCLUDED.text,
                            embedding = EXCLUDED.embedding,
                            metadata_extra = EXCLUDED.metadata_extra
                    """),
                    {
                        "corpus": corpus,
                        "tenant_id": tenant_id,
                        "doc_id": meta.get("doc_id", meta["pdf_id"]),
                        "pdf_id": meta["pdf_id"],
                        "page": meta["page"],
                        "chunk_id": chunk_id,
                        "source_file": meta["source_file"],
                        "text": text,
                        "embedding": vec_str,
                        "metadata_extra": json.dumps(extra) if extra else None,
                    },
                )

            print(f"  Inserted {batch_end}/{len(all_ids)} chunks")

    engine.dispose()
    print(f"Index built: {len(all_ids)} chunks inserted into PostgreSQL (corpus={corpus})")


if __name__ == "__main__":
    build_index()
