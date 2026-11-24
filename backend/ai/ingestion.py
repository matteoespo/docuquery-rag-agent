import base64
import glob
import hashlib
import os
import threading
import time
from pathlib import Path

import pdfplumber
import pymupdf
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage
from langchain_text_splitters import RecursiveCharacterTextSplitter

from ai.llm import get_embeddings, get_vision_llm
from core.config import settings
from core.logger import get_logger

logger = get_logger(__name__)

# Ingestion status tracking (thread-safe, read via get_ingestion_status())
_status_lock = threading.Lock()
_ingestion_status: dict = {
    "phase": "idle",      # "idle" | "text" | "images" | "complete"
    "detail": "",
    "images_done": 0,
    "images_total": 0,
}


def get_ingestion_status() -> dict:
    """Return a snapshot of the current ingestion status."""
    with _status_lock:
        return dict(_ingestion_status)


def _update_status(**kwargs):
    with _status_lock:
        _ingestion_status.update(kwargs)


def _increment_images_done():
    """Atomically increment the images_done counter."""
    with _status_lock:
        _ingestion_status["images_done"] += 1


def _file_hash(file_path: str) -> str:
    """Return a short SHA-256 hex digest for deduplication."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            h.update(block)
    return h.hexdigest()[:16]


# Image helpers
def _should_caption_image(image_bytes: bytes, img_metadata: dict) -> bool:
    """Filter out small/decorative images that add no retrieval value."""
    if len(image_bytes) < settings.min_image_bytes:
        return False

    width = img_metadata.get("width", 0)
    height = img_metadata.get("height", 0)
    if width < settings.min_image_dimension and height < settings.min_image_dimension:
        return False

    return True


def extract_image_caption(image_bytes: bytes) -> str:
    """Generate a caption for an image using Moondream."""
    vision_llm = get_vision_llm()
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    message = HumanMessage(
        content=[
            {"type": "text", "text": "Describe this image in detail. Extract any relevant technical information."},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
        ]
    )

    try:
        response = vision_llm.invoke([message])
        return response.content
    except Exception as e:
        logger.error("Vision model error: %s", e)
        return "Image description unavailable."

# Table helpers
def table_to_markdown(table_data) -> str:
    """Converts a parsed pdfplumber table into a Markdown string."""
    md = "\n"
    for i, row in enumerate(table_data):
        clean_row = [str(item).replace("\n", " ").strip() if item else "" for item in row]
        md += "| " + " | ".join(clean_row) + " |\n"
        if i == 0:
            md += "|" + "|".join(["---"] * len(clean_row)) + "|\n"
    return md + "\n"


# Phase 1: text + tables
def _extract_text_and_tables(file_path: str) -> list[Document]:
    """Extract text and tables from a PDF. No Moondream calls."""
    documents = []
    with pdfplumber.open(file_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            page_content = page.extract_text() or ""

            tables = page.extract_tables()
            for table in tables:
                page_content += table_to_markdown(table)

            if page_content.strip():
                doc = Document(
                    page_content=page_content,
                    metadata={"source": file_path, "page": page_num + 1}
                )
                documents.append(doc)
    return documents


def _get_vector_db() -> Chroma:
    return Chroma(persist_directory=settings.db_dir, embedding_function=get_embeddings())


def _split_documents(documents: list[Document]) -> list[Document]:
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150,
        separators=["\n\n", "\n", ".", " ", ""]
    )
    return text_splitter.split_documents(documents)


def _chunk_ids(prefix: str, chunks: list[Document]) -> list[str]:
    """IDs that depend only on this file's content: ``{prefix}_{page}_{n}``.

    ``n`` counts chunks within the same page, so IDs never shift when other
    files are added or removed.
    """
    per_page: dict = {}
    ids = []
    for chunk in chunks:
        page = chunk.metadata["page"]
        n = per_page.get(page, 0)
        per_page[page] = n + 1
        ids.append(f"{prefix}_{page}_{n}")
    return ids


def _add_in_batches(vector_db: Chroma, chunks: list[Document], ids: list[str], label: str) -> None:
    batch_size = settings.chroma_batch_size
    total_batches = (len(chunks) + batch_size - 1) // batch_size
    for batch_num, i in enumerate(range(0, len(chunks), batch_size), start=1):
        vector_db.add_documents(chunks[i : i + batch_size], ids=ids[i : i + batch_size])
        logger.info("  %s batch %d/%d", label, batch_num, total_batches)


def _is_already_ingested(vector_db: Chroma, source: str, file_hash: str) -> bool:
    """Return True if ``source`` is fully indexed with this exact content.

    Vectors for ``source`` from different content (file overwritten) or from
    before ``file_hash`` metadata existed are deleted so the file is re-indexed
    cleanly instead of accumulating stale chunks.
    """
    existing = vector_db._collection.get(where={"source": source}, include=["metadatas"])
    if not existing["ids"]:
        return False
    if all((m or {}).get("file_hash") == file_hash for m in existing["metadatas"]):
        return True
    vector_db._collection.delete(ids=existing["ids"])
    logger.info("Removed %d stale vectors for %s", len(existing["ids"]), os.path.basename(source))
    return False


def ingest_manual(file_paths: list[str] | None = None) -> list[str]:
    """
    Phase 1: extract text + tables, chunk, embed into Chroma.

    Only ``file_paths`` are processed (defaults to every PDF under
    ``settings.manual_path``). Files whose current content is already indexed
    are skipped. Returns the files that were newly ingested, so Phase 2 only
    captions images for those.
    """
    phase1_start = time.perf_counter()
    _update_status(phase="text", detail="Extracting text and tables...",
                   images_done=0, images_total=0)

    if file_paths is None:
        if not os.path.exists(settings.manual_path):
            logger.error("Manual path not found: %s", settings.manual_path)
            _update_status(phase="idle", detail="")
            return []
        file_paths = glob.glob(os.path.join(settings.manual_path, "**/*.pdf"), recursive=True)

    # Normalise so "source" metadata matches what delete_document() looks up.
    file_paths = [str(Path(fp)) for fp in file_paths]
    if not file_paths:
        logger.warning("No PDF files found.")
        _update_status(phase="idle", detail="")
        return []

    vector_db = _get_vector_db()
    ingested: list[str] = []
    total_chunks = 0

    for file_path in file_paths:
        start = time.perf_counter()
        file_hash = _file_hash(file_path)
        name = os.path.basename(file_path)

        if _is_already_ingested(vector_db, file_path, file_hash):
            logger.info("  - %s already indexed, skipping", name)
            continue

        documents = _extract_text_and_tables(file_path)
        chunks = _split_documents(documents)
        for chunk in chunks:
            chunk.metadata["file_hash"] = file_hash

        if chunks:
            _add_in_batches(vector_db, chunks, _chunk_ids(file_hash, chunks), label=name)
        total_chunks += len(chunks)
        ingested.append(file_path)
        logger.info("  ✓ %s — %d pages, %d chunks — %.1fs",
                    name, len(documents), len(chunks), time.perf_counter() - start)

    elapsed = time.perf_counter() - phase1_start
    logger.info("Phase 1 complete: %d/%d PDFs ingested, %d chunks in %.1fs",
                len(ingested), len(file_paths), total_chunks, elapsed)

    if not ingested:
        _update_status(phase="complete", detail="All files were already indexed")
    return ingested


# Phase 2: image captioning
def _extract_and_caption_images(file_path: str) -> list[Document]:
    """Extract images from a PDF, filter, caption with Moondream."""
    documents = []
    filename = os.path.basename(file_path)

    pdf_document = pymupdf.open(file_path)

    for page_num in range(len(pdf_document)):
        page = pdf_document[page_num]
        image_list = page.get_images(full=True)
        captions = []

        for img_index, img in enumerate(image_list):
            xref = img[0]
            base_image = pdf_document.extract_image(xref)
            image_bytes = base_image["image"]

            if not _should_caption_image(image_bytes, base_image):
                continue

            caption = extract_image_caption(image_bytes)
            captions.append(f"[Image {img_index + 1} Caption]: {caption}")

            _increment_images_done()

        if captions:
            doc = Document(
                page_content="\n".join(captions),
                metadata={"source": file_path, "page": page_num + 1, "type": "image_captions"}
            )
            documents.append(doc)

    pdf_document.close()

    logger.info("%s — %d image caption chunks", filename, len(documents))
    return documents


def enrich_with_images(pdf_files: list[str]):
    """
    Phase 2 (background): caption images with Moondream and upsert
    supplementary chunks into the existing Chroma DB.
    """
    if settings.skip_image_captioning:
        _update_status(phase="complete", detail="Image captioning skipped")
        logger.info("Image captioning skipped (SKIP_IMAGE_CAPTIONING=true)")
        return

    phase2_start = time.perf_counter()

    # Count total images to caption (for progress tracking)
    total_images = 0
    for file_path in pdf_files:
        pdf_doc = pymupdf.open(file_path)
        for page_num in range(len(pdf_doc)):
            page = pdf_doc[page_num]
            for img in page.get_images(full=True):
                xref = img[0]
                base_image = pdf_doc.extract_image(xref)
                if _should_caption_image(base_image["image"], base_image):
                    total_images += 1
        pdf_doc.close()

    _update_status(phase="images", detail="Captioning images in background...",
                   images_done=0, images_total=total_images)
    logger.info("Phase 2: Captioning %d images across %d PDFs...", total_images, len(pdf_files))

    chunks: list[Document] = []
    chunk_ids: list[str] = []
    for file_path in pdf_files:
        start = time.perf_counter()
        file_hash = _file_hash(file_path)
        file_chunks = _split_documents(_extract_and_caption_images(file_path))
        for chunk in file_chunks:
            chunk.metadata["file_hash"] = file_hash
        chunks.extend(file_chunks)
        # img_ prefix avoids collisions with the Phase 1 text chunk IDs.
        chunk_ids.extend(_chunk_ids(f"img_{file_hash}", file_chunks))
        logger.info("    (%s — %.1fs)", os.path.basename(file_path), time.perf_counter() - start)

    if not chunks:
        _update_status(phase="complete", detail="No captionable images found")
        logger.info("No images found to caption.")
        return

    _add_in_batches(_get_vector_db(), chunks, chunk_ids, label="Image")

    elapsed = time.perf_counter() - phase2_start
    _update_status(phase="complete",
                   detail=f"Done — {len(chunks)} image chunks in {elapsed:.1f}s")
    logger.info("Phase 2 complete: %d image chunks added in %.1fs", len(chunks), elapsed)


def delete_document_vectors(file_path: str) -> int:
    """Delete all ChromaDB vectors associated with the given PDF file path.

    Returns the number of deleted vectors.
    """
    collection = _get_vector_db()._collection

    results = collection.get(where={"source": file_path})
    matching_ids = results["ids"]

    if not matching_ids:
        logger.info("No vectors found for source: %s", file_path)
        return 0

    collection.delete(ids=matching_ids)
    logger.info("Deleted %d vectors for source: %s", len(matching_ids), file_path)
    return len(matching_ids)


if __name__ == "__main__":
    # Re-index everything in MANUAL_PATH: skips files already indexed with
    # their current content, and replaces stale/legacy vectors for the rest.
    # Run from backend/:  python -m ai.ingestion
    enrich_with_images(ingest_manual())
