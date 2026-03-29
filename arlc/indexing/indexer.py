"""Index PDF documents into ChromaDB and/or FAISS for retrieval."""

import os
import re
import json
import shutil
import base64
import pymupdf
import chromadb
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
from chromadb.utils import embedding_functions
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
    re.compile(r'\b((?:CFI|CA|ARB|ENF|SCT|TCD|DEC)[\s\-_]*\d+[\s/\-_]*\d+)\b', re.IGNORECASE),
    # Article references: Article 14, Article 14(2)(b)
    re.compile(r'\b(Article\s+\d+(?:\(\w+\))*)\b', re.IGNORECASE),
    # Law number references: Law No. 5 of 2020, DIFC Law No. 2
    re.compile(r'\b((?:DIFC\s+)?Law\s+No\.?\s*\d+(?:\s+of\s+\d+)?)\b', re.IGNORECASE),
    # Regulation references: Regulation No. 1
    re.compile(r'\b(Regulation\s+No\.?\s*\d+)\b', re.IGNORECASE),
]


def extract_entities_from_chunk(text: str) -> list[str]:
    """Extract legal entities (case IDs, article refs, law names) from chunk text.

    Returns deduplicated list of entity strings, normalized to lowercase.
    Used at index time to populate the 'entities' metadata field.
    """
    entities: set[str] = set()
    for pattern in _ENTITY_PATTERNS:
        for match in pattern.findall(text):
            entity = re.sub(r'\s+', ' ', match.strip()).lower()
            if entity:
                entities.add(entity)
    return sorted(entities)


DOCUMENTS_DIR = "data/documents"
CHROMA_DIR = "data/chroma_db"
# Snowflake Arctic Embed L v2.0: 1024-dim, retrieval-optimized (2024), replaces BGE-large-en-v1.5
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "Snowflake/snowflake-arctic-embed-l-v2.0")
# FAISS: pure vector math, no SQLite overhead — strictly better than ChromaDB for ~27K vectors
# Credit: FAISS backend choice inspired by IAS Partners (guy4)
FAISS_INDEX_PATH = "data/faiss_index.bin"
FAISS_METADATA_PATH = "data/faiss_metadata.json"
# VECTOR_BACKEND: "faiss" (default, preferred) or "chroma" (fallback)
VECTOR_BACKEND = os.environ.get("VECTOR_BACKEND", "faiss")

_ocr_model = os.environ.get("MODEL_NAME", "")

_doc_summary_cache: dict[str, str] = {}

# Embedding decontamination insight from guy3 (structure-first methodology)
# Boilerplate patterns that dominate embedding space, making all pages of the
# same document cluster together instead of discriminating by content.
_BOILERPLATE_PATTERNS = [
    re.compile(r'IN\s+THE\s+DUBAI\s+INTERNATIONAL\s+FINANCIAL\s+CENTRE\s+COURTS?', re.IGNORECASE),
    re.compile(r'IN\s+THE\s+COURT\s+OF\s+FIRST\s+INSTANCE', re.IGNORECASE),
    re.compile(r'IN\s+THE\s+SMALL\s+CLAIMS\s+TRIBUNAL', re.IGNORECASE),
    re.compile(r'COURT\s+OF\s+APPEAL', re.IGNORECASE),
    re.compile(r'(?:Claim|Case)\s+No\s*:\s*\S+', re.IGNORECASE),
    re.compile(r'^BETWEEN\s*$', re.MULTILINE | re.IGNORECASE),
    re.compile(r'^(?:Claimant|Defendant|Respondent|Applicant)s?\s*$', re.MULTILINE | re.IGNORECASE),
    re.compile(r'Page\s+\d+\s+of\s+\d+', re.IGNORECASE),
    re.compile(r'^\s*\d{1,3}\s*$', re.MULTILINE),  # standalone page numbers
    re.compile(r'^\s*\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}\s*$', re.MULTILINE),  # date stamps on their own line
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
        cleaned = re.sub(re.escape(title), '', cleaned, flags=re.IGNORECASE)

    # Strip known boilerplate patterns
    for pattern in _BOILERPLATE_PATTERNS:
        cleaned = pattern.sub('', cleaned)

    # Collapse excessive whitespace left by removals
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    cleaned = cleaned.strip()

    return cleaned


# Legal structure header pattern for structure-aware chunking
_LEGAL_HEADER_PATTERN = re.compile(
    r'(?=\n(?:Article|Section|Part|Schedule|Appendix|Chapter)\s+[\dIVXivx]+)',
    re.IGNORECASE
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
    r'^((?:Article|Section|Part|Schedule|Appendix|Chapter)\s+[\dIVXivx]+[^.\n]{0,80})',
    re.IGNORECASE
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
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": img_b64}},
                    {"type": "text",
                     "text": "Extract all text from this legal document page. Return only the extracted text, no commentary."}
                ]
            }],
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
        paragraphs = [p.strip() for p in re.split(r'\n{2,}', text) if p.strip()]

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
                sentences = re.split(r'(?<=[.!?])\s+', para)

                # If no sentence boundaries found (e.g., legal lists with semicolons),
                # try splitting on semicolons or line breaks
                if len(sentences) == 1:
                    # Try semicolon splits for legal lists
                    sentences = [s.strip() + ';' if i < len(para.split(';')) - 1 else s.strip()
                                 for i, s in enumerate(para.split(';')) if s.strip()]

                # If still one giant chunk, force split at max_chars
                if len(sentences) == 1 and len(sentences[0]) > max_chars:
                    # Hard split as last resort
                    text = sentences[0]
                    while text:
                        chunk_size = max_chars if len(text) > max_chars else len(text)
                        chunks.append(text[:chunk_size])
                        text = text[chunk_size:]
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
                                text = sent
                                while text:
                                    chunk_size = max_chars if len(text) > max_chars else len(text)
                                    chunks.append(text[:chunk_size])
                                    text = text[chunk_size:]
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
    """Extract text from each page of a PDF, returning paragraph-level chunks."""
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


def _get_embedding_function():
    """Get the SentenceTransformer embedding model with GPU auto-detection.

    Uses SentenceTransformer directly (not chromadb's wrapper) so we can
    control the device — CUDA > MPS > CPU.  Arctic Embed v2.0 requires
    trust_remote_code=True.
    """
    import torch
    from sentence_transformers import SentenceTransformer

    device = (
        'cuda' if torch.cuda.is_available()
        else 'mps' if torch.backends.mps.is_available()
        else 'cpu'
    )
    model_kwargs = {}
    if "arctic" in EMBEDDING_MODEL.lower():
        model_kwargs["trust_remote_code"] = True
    model = SentenceTransformer(EMBEDDING_MODEL, device=device, **model_kwargs)
    print(f"  Embedding model loaded on {device}")

    def encode(texts: list[str]) -> list[list[float]]:
        embeddings = model.encode(texts, normalize_embeddings=True,
                                  batch_size=256, show_progress_bar=True)
        return embeddings.tolist()

    return encode


def build_index():
    """Build vector index from all PDF documents.

    Builds FAISS index by default (VECTOR_BACKEND=faiss). Set VECTOR_BACKEND=chroma
    for ChromaDB fallback. Both backends can be built simultaneously if desired.
    """
    ef = _get_embedding_function()

    # Clear BM25 disk cache — it will be rebuilt after indexing
    bm25_cache = "data/bm25_cache"
    if os.path.exists(bm25_cache):
        shutil.rmtree(bm25_cache)

    # ChromaDB setup (always built for backward compat; FAISS is added alongside)
    client = chromadb.PersistentClient(path=CHROMA_DIR)

    # Delete existing collection if it exists
    try:
        client.delete_collection("legal_docs")
    except Exception:
        pass

    # ChromaDB collection — we pass pre-computed embeddings so no embedding_function needed.
    # Query-time uses FAISS, not ChromaDB. Kept for backward compat only.
    chroma_ef = None
    if "arctic" in EMBEDDING_MODEL.lower():
        chroma_ef_kwargs = {"trust_remote_code": True}
    else:
        chroma_ef_kwargs = {}
    try:
        chroma_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL, **chroma_ef_kwargs)
    except Exception:
        pass  # ChromaDB query-time embedding not critical — FAISS is primary
    collection = client.create_collection(
        name="legal_docs",
        embedding_function=chroma_ef,
        metadata={"hnsw:space": "cosine"},
    )

    pdf_files = sorted(f for f in os.listdir(DOCUMENTS_DIR) if f.endswith(".pdf"))
    print(f"Indexing {len(pdf_files)} PDF files (backend={VECTOR_BACKEND}, model={EMBEDDING_MODEL})...")

    all_ids = []
    all_texts = []
    all_metadatas = []
    # (idx, pdf_id, summary, chunk_text, chunk_key) for concurrent context generation
    pending_contexts = []

    for pdf_file in pdf_files:
        pdf_id = pdf_file.replace(".pdf", "")
        pdf_path = os.path.join(DOCUMENTS_DIR, pdf_file)
        chunks = extract_pages(pdf_path)

        # SAC: generate per-document summary from first 2-3 pages
        first_pages_text = "\n\n".join(
            c["text"] for c in chunks if c["page"] <= 3
        )
        summary = _generate_doc_summary(pdf_id, first_pages_text) if first_pages_text else ""
        if summary:
            print(f"  SAC summary for {pdf_file}: {summary}")

        for chunk_info in chunks:
            chunk_id = f"{pdf_id}_{chunk_info['page']}_{chunk_info['chunk_idx']}"
            all_ids.append(chunk_id)
            all_texts.append(chunk_info["text"])  # raw text; SAC prefix prepended below
            # Entity extraction at index time (inspired by CPBD, Azamat Yelmagambetov, 1st place)
            # Stored as pipe-separated string (ChromaDB metadata requires scalar values).
            entities = extract_entities_from_chunk(chunk_info["text"])
            all_metadatas.append({
                "pdf_id": pdf_id,
                "page": chunk_info["page"],  # 1-based, used for grounding
                "source_file": pdf_file,
                "entities": "|".join(entities),  # pipe-separated for ChromaDB scalar compat
            })
            if summary:
                chunk_key = f"{chunk_info['page']}_{chunk_info['chunk_idx']}"
                pending_contexts.append((len(all_ids) - 1, pdf_id, summary,
                                         chunk_info["text"], chunk_key))

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

    # Embedding decontamination: clean text for embedding, keep original for storage/BM25
    print("  Cleaning text for embedding decontamination...")
    all_embed_texts = []
    for i, text in enumerate(all_texts):
        meta = all_metadatas[i]
        doc_meta = {"title": meta.get("pdf_id", "").replace("_", " ")}
        all_embed_texts.append(clean_text_for_embedding(text, doc_meta))

    # Pre-compute embeddings from cleaned text
    print("  Computing embeddings from decontaminated text...")
    all_embeddings = ef(all_embed_texts)

    # --- Build FAISS index ---
    if VECTOR_BACKEND == "faiss" or os.environ.get("BUILD_BOTH_BACKENDS"):
        import faiss

        print("  Building FAISS index...")
        embeddings_np = np.array(all_embeddings).astype('float32')
        faiss.normalize_L2(embeddings_np)  # normalize for cosine similarity via inner product
        dim = embeddings_np.shape[1]
        index = faiss.IndexFlatIP(dim)  # inner product on L2-normalized vectors = cosine similarity
        index.add(embeddings_np)
        faiss.write_index(index, FAISS_INDEX_PATH)
        print(f"  FAISS index saved: {FAISS_INDEX_PATH} ({index.ntotal} vectors, {dim}-dim)")

        # Save metadata mapping: index position -> {chunk_id, doc_id, page, text, entities}
        faiss_metadata = []
        for i in range(len(all_ids)):
            faiss_metadata.append({
                "chunk_id": all_ids[i],
                "pdf_id": all_metadatas[i]["pdf_id"],
                "page": all_metadatas[i]["page"],
                "source_file": all_metadatas[i]["source_file"],
                "text": all_texts[i],
                # Entities extracted at index time (pipe-separated string)
                "entities": all_metadatas[i].get("entities", ""),
            })
        with open(FAISS_METADATA_PATH, "w") as f:
            json.dump(faiss_metadata, f)
        print(f"  FAISS metadata saved: {FAISS_METADATA_PATH} ({len(faiss_metadata)} entries)")

    # --- Build ChromaDB index (always, for backward compat) ---
    # Add in batches — store ORIGINAL text but use CLEANED embeddings
    batch_size = 100
    for i in range(0, len(all_ids), batch_size):
        end = min(i + batch_size, len(all_ids))
        collection.add(
            ids=all_ids[i:end],
            documents=all_texts[i:end],
            embeddings=all_embeddings[i:end],
            metadatas=all_metadatas[i:end],
        )
        print(f"  Indexed {end}/{len(all_ids)} chunks (ChromaDB)")

    print(f"Done! Total chunks: {len(all_ids)}")
    return collection


if __name__ == "__main__":
    build_index()
