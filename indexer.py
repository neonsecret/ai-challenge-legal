"""Index PDF documents into ChromaDB for retrieval."""

import os
import re
import shutil
import base64
import pymupdf
import chromadb
import anthropic
from concurrent.futures import ThreadPoolExecutor, as_completed
from chromadb.utils import embedding_functions
from dotenv import load_dotenv

load_dotenv()

DOCUMENTS_DIR = "data/documents"
CHROMA_DIR = "data/chroma_db"
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-large-en-v1.5")

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
        response = anthropic.completion(
            model=os.environ["MODEL_NAME"],
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=80,
            timeout=45,
        )
        summary = response.choices[0].message.content.strip()
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
        response = anthropic.completion(
            model=os.environ["MODEL_NAME"],
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=40,
            timeout=18,
        )
        context = response.choices[0].message.content.strip()
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

        # Call vision API
        response = anthropic.completion(
            model=_ocr_model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
                    {"type": "text", "text": "Extract all text from this legal document page. Return only the extracted text, no commentary."}
                ]
            }],
            max_tokens=2048,
        )

        text = response.choices[0].message.content.strip()
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


def build_index():
    """Build ChromaDB index from all PDF documents."""
    ef = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name=EMBEDDING_MODEL
    )

    # Clear BM25 disk cache — it will be rebuilt after indexing
    bm25_cache = "data/bm25_cache"
    if os.path.exists(bm25_cache):
        shutil.rmtree(bm25_cache)

    client = chromadb.PersistentClient(path=CHROMA_DIR)

    # Delete existing collection if it exists
    try:
        client.delete_collection("legal_docs")
    except Exception:
        pass

    collection = client.create_collection(
        name="legal_docs",
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )

    pdf_files = sorted(f for f in os.listdir(DOCUMENTS_DIR) if f.endswith(".pdf"))
    print(f"Indexing {len(pdf_files)} PDF files...")

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
            all_metadatas.append({
                "pdf_id": pdf_id,
                "page": chunk_info["page"],   # 1-based, used for grounding
                "source_file": pdf_file,
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
        print(f"  Indexed {end}/{len(all_ids)} chunks")

    print(f"Done! Total chunks: {len(all_ids)}")
    return collection


if __name__ == "__main__":
    build_index()
