import os
import glob
import base64
import time
import threading
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_core.messages import HumanMessage
import core.config as config
from ai.llm import get_embeddings, get_vision_llm
import fitz
import pdfplumber

load_dotenv()

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


# Image helpers
def _should_caption_image(image_bytes: bytes, img_metadata: dict) -> bool:
    """Filter out small/decorative images that add no retrieval value."""
    if len(image_bytes) < config.MIN_IMAGE_BYTES:
        return False

    width = img_metadata.get("width", 0)
    height = img_metadata.get("height", 0)
    if width < config.MIN_IMAGE_DIMENSION and height < config.MIN_IMAGE_DIMENSION:
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
        print(f"Vision model error: {e}")
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

    if not os.path.exists(config.MANUAL_PATH):
        print(f"Error: {config.MANUAL_PATH} not found")
        _update_status(phase="idle", detail="")
        return []

    pdf_files = glob.glob(os.path.join(config.MANUAL_PATH, "**/*.pdf"), recursive=True)
    if not pdf_files:
        print("No PDF files found.")
        _update_status(phase="idle", detail="")
        return []

    documents = []
    print(f"Found {len(pdf_files)} PDFs. Extracting text and tables...")

    for file_path in pdf_files:
        start = time.perf_counter()
        docs = _extract_text_and_tables(file_path)
        documents.extend(docs)
        elapsed = time.perf_counter() - start
        print(f"  ✓ {os.path.basename(file_path)} — {len(docs)} pages — {elapsed:.1f}s")

    print(f"Loaded {len(documents)} pages")

    # Split into chunks
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150,
        separators=["\n\n", "\n", ".", " ", ""]
    )
    chunks = text_splitter.split_documents(documents)
    print(f"Document split into {len(chunks)} chunks")

    # Prepare chunk IDs
    chunk_ids = [
        f"{chunk.metadata['source']}_{chunk.metadata['page']}_{i}"
        for i, chunk in enumerate(chunks)
    ]

    # Embedding model
    embeddings = get_embeddings()

    # Vector DB batched writes
    vector_db = Chroma(persist_directory=config.DB_DIR, embedding_function=embeddings)
    total_batches = (len(chunks) + config.CHROMA_BATCH_SIZE - 1) // config.CHROMA_BATCH_SIZE

    for batch_num, i in enumerate(range(0, len(chunks), config.CHROMA_BATCH_SIZE), start=1):
        batch = chunks[i : i + config.CHROMA_BATCH_SIZE]
        batch_ids = chunk_ids[i : i + config.CHROMA_BATCH_SIZE]
        vector_db.add_documents(batch, ids=batch_ids)
        print(
            f"  Embedded batch {batch_num}/{total_batches} "
            f"({min(i + config.CHROMA_BATCH_SIZE, len(chunks))}/{len(chunks)} chunks)"
        )

    elapsed = time.perf_counter() - phase1_start
    print(f"Phase 1 complete: {len(pdf_files)} PDFs, {len(chunks)} chunks in {elapsed:.1f}s")

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

            _update_status(images_done=_ingestion_status["images_done"] + 1)

        if captions:
            doc = Document(
                page_content="\n".join(captions),
                metadata={"source": file_path, "page": page_num + 1, "type": "image_captions"}
            )
            documents.append(doc)

    pdf_document.close()

    print(f"{filename} — {len(documents)} image caption chunks")
    return documents


def enrich_with_images(pdf_files: list[str]):
    """
    Phase 2 (background): caption images with Moondream and upsert
    supplementary chunks into the existing Chroma DB.
    """
    if config.SKIP_IMAGE_CAPTIONING:
        _update_status(phase="complete", detail="Image captioning skipped")
        print("Image captioning skipped (SKIP_IMAGE_CAPTIONING=true)")
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
    print(f"Phase 2: Captioning {total_images} images across {len(pdf_files)} PDFs...")

    all_image_docs = []
    for file_path in pdf_files:
        start = time.perf_counter()
        docs = _extract_and_caption_images(file_path)
        all_image_docs.extend(docs)
        elapsed = time.perf_counter() - start
        print(f"    ({os.path.basename(file_path)} — {elapsed:.1f}s)")

    if not all_image_docs:
        _update_status(phase="complete", detail="No captionable images found")
        print("No images found to caption.")
        return

    # Chunk the caption documents
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=150,
        separators=["\n\n", "\n", ".", " ", ""]
    )
    chunks = text_splitter.split_documents(all_image_docs)

    # Unique IDs prefixed with img_ to avoid collisions with Phase 1
    chunk_ids = [
        f"img_{chunk.metadata['source']}_{chunk.metadata['page']}_{i}"
        for i, chunk in enumerate(chunks)
    ]

    # Upsert into existing Chroma DB
    embeddings = get_embeddings()
    vector_db = Chroma(persist_directory=config.DB_DIR, embedding_function=embeddings)

    total_batches = (len(chunks) + config.CHROMA_BATCH_SIZE - 1) // config.CHROMA_BATCH_SIZE
    for batch_num, i in enumerate(range(0, len(chunks), config.CHROMA_BATCH_SIZE), start=1):
        batch = chunks[i : i + config.CHROMA_BATCH_SIZE]
        batch_ids = chunk_ids[i : i + config.CHROMA_BATCH_SIZE]
        vector_db.add_documents(batch, ids=batch_ids)
        print(f"  Image batch {batch_num}/{total_batches}")

    elapsed = time.perf_counter() - phase2_start
    _update_status(phase="complete",
                   detail=f"Done — {len(chunks)} image chunks in {elapsed:.1f}s")
    print(f"Phase 2 complete: {len(chunks)} image chunks added in {elapsed:.1f}s")

