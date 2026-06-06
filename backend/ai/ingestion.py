import os
import glob
import base64
import hashlib
import time
import threading
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_core.messages import HumanMessage
from core.config import settings
from core.logger import get_logger
from ai.llm import get_embeddings, get_vision_llm
import fitz
import pdfplumber

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


def ingest_manual() -> list[str]:
    """
    Phase 1: extract text + tables, chunk, embed into Chroma.
    Returns the list of PDF file paths so Phase 2 can caption images later.
    """
    phase1_start = time.perf_counter()
    _update_status(phase="text", detail="Extracting text and tables...",
                   images_done=0, images_total=0)

    if not os.path.exists(settings.manual_path):
        logger.error("Manual path not found: %s", settings.manual_path)
        _update_status(phase="idle", detail="")
        return []

    pdf_files = glob.glob(os.path.join(settings.manual_path, "**/*.pdf"), recursive=True)
    if not pdf_files:
        logger.warning("No PDF files found.")
        _update_status(phase="idle", detail="")
        return []

    documents = []
    logger.info("Found %d PDFs. Extracting text and tables...", len(pdf_files))

    for file_path in pdf_files:
        start = time.perf_counter()
        docs = _extract_text_and_tables(file_path)
        documents.extend(docs)
        elapsed = time.perf_counter() - start
        logger.info("  ✓ %s — %d pages — %.1fs", os.path.basename(file_path), len(docs), elapsed)

    logger.info("Loaded %d pages", len(documents))

    # Split into chunks
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150,
        separators=["\n\n", "\n", ".", " ", ""]
    )
    chunks = text_splitter.split_documents(documents)
    logger.info("Document split into %d chunks", len(chunks))

    # Prepare chunk IDs (hash-based for deduplication)
    file_hashes = {fp: _file_hash(fp) for fp in pdf_files}
    chunk_ids = [
        f"{file_hashes[chunk.metadata['source']]}_{chunk.metadata['page']}_{i}"
        for i, chunk in enumerate(chunks)
    ]

    # Embedding model
    embeddings = get_embeddings()

    # Vector DB batched writes
    vector_db = Chroma(persist_directory=settings.db_dir, embedding_function=embeddings)
    total_batches = (len(chunks) + settings.chroma_batch_size - 1) // settings.chroma_batch_size

    for batch_num, i in enumerate(range(0, len(chunks), settings.chroma_batch_size), start=1):
        batch = chunks[i : i + settings.chroma_batch_size]
        batch_ids = chunk_ids[i : i + settings.chroma_batch_size]
        vector_db.add_documents(batch, ids=batch_ids)
        logger.info(
            "  Embedded batch %d/%d (%d/%d chunks)",
            batch_num, total_batches,
            min(i + settings.chroma_batch_size, len(chunks)), len(chunks)
        )

    elapsed = time.perf_counter() - phase1_start
    logger.info("Phase 1 complete: %d PDFs, %d chunks in %.1fs", len(pdf_files), len(chunks), elapsed)

    return pdf_files


# Phase 2: image captioning
def _extract_and_caption_images(file_path: str) -> list[Document]:
    """Extract images from a PDF, filter, caption with Moondream."""
    documents = []
    filename = os.path.basename(file_path)

    pdf_document = fitz.open(file_path)

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
        pdf_doc = fitz.open(file_path)
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

    all_image_docs = []
    for file_path in pdf_files:
        start = time.perf_counter()
        docs = _extract_and_caption_images(file_path)
        all_image_docs.extend(docs)
        elapsed = time.perf_counter() - start
        logger.info("    (%s — %.1fs)", os.path.basename(file_path), elapsed)

    if not all_image_docs:
        _update_status(phase="complete", detail="No captionable images found")
        logger.info("No images found to caption.")
        return

    # Chunk the caption documents
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150,
        separators=["\n\n", "\n", ".", " ", ""]
    )
    chunks = text_splitter.split_documents(all_image_docs)

    # Unique IDs prefixed with img_ to avoid collisions with Phase 1
    file_hashes = {fp: _file_hash(fp) for fp in pdf_files}
    chunk_ids = [
        f"img_{file_hashes[chunk.metadata['source']]}_{chunk.metadata['page']}_{i}"
        for i, chunk in enumerate(chunks)
    ]

    # Upsert into existing Chroma DB
    embeddings = get_embeddings()
    vector_db = Chroma(persist_directory=settings.db_dir, embedding_function=embeddings)

    total_batches = (len(chunks) + settings.chroma_batch_size - 1) // settings.chroma_batch_size
    for batch_num, i in enumerate(range(0, len(chunks), settings.chroma_batch_size), start=1):
        batch = chunks[i : i + settings.chroma_batch_size]
        batch_ids = chunk_ids[i : i + settings.chroma_batch_size]
        vector_db.add_documents(batch, ids=batch_ids)
        logger.info("  Image batch %d/%d", batch_num, total_batches)

    elapsed = time.perf_counter() - phase2_start
    _update_status(phase="complete",
                   detail=f"Done — {len(chunks)} image chunks in {elapsed:.1f}s")
    logger.info("Phase 2 complete: %d image chunks added in %.1fs", len(chunks), elapsed)


def delete_document_vectors(file_path: str) -> int:
    """Delete all ChromaDB vectors associated with the given PDF file path.

    Returns the number of deleted vectors.
    """
    vector_db = Chroma(persist_directory=settings.db_dir, embedding_function=get_embeddings())
    collection = vector_db._collection

    results = collection.get(where={"source": file_path})
    matching_ids = results["ids"]

    if not matching_ids:
        logger.info("No vectors found for source: %s", file_path)
        return 0

    collection.delete(ids=matching_ids)
    logger.info("Deleted %d vectors for source: %s", len(matching_ids), file_path)
    return len(matching_ids)
