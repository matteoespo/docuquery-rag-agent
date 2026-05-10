import os
import glob
import base64
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

def table_to_markdown(table_data) -> str:
    """Converts a parsed pdfplumber table into a Markdown string."""
    md = "\n"
    for i, row in enumerate(table_data):
        clean_row = [str(item).replace("\n", " ").strip() if item else "" for item in row]
        md += "| " + " | ".join(clean_row) + " |\n"
        if i == 0:
            md += "|" + "|".join(["---"] * len(clean_row)) + "|\n"
    return md + "\n"

def process_pdf(file_path: str) -> list[Document]:
    """Extracts text, markdown tables, and image captions from a PDF."""
    documents = []
    
    # Extract Images via PyMuPDF
    pdf_document = fitz.open(file_path)
    image_captions_by_page = {}
    
    for page_num in range(len(pdf_document)):
        page = pdf_document[page_num]
        image_list = page.get_images(full=True)
        captions = []
        
        for img_index, img in enumerate(image_list):
            xref = img[0]
            base_image = pdf_document.extract_image(xref)
            image_bytes = base_image["image"]
            caption = extract_image_caption(image_bytes)
            captions.append(f"[Image {img_index + 1} Caption]: {caption}")
            
        image_captions_by_page[page_num] = "\n".join(captions)
        
    pdf_document.close()

    # Extract Text and Tables via pdfplumber
    with pdfplumber.open(file_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            page_content = page.extract_text() or ""
            
            # Extract tables and append as Markdown
            tables = page.extract_tables()
            for table in tables:
                page_content += table_to_markdown(table)
                
            # Append Image Captions
            if image_captions_by_page.get(page_num):
                page_content += "\n\n" + image_captions_by_page[page_num]
                
            if page_content.strip():
                doc = Document(
                    page_content=page_content,
                    metadata={"source": file_path, "page": page_num + 1}
                )
                documents.append(doc)
                
    return documents

def ingest_manual():
    """
    Loads PDFs, extracts text/tables/images, splits into chunks and stores embeddings.
    """
    if not os.path.exists(config.MANUAL_PATH):
        print(f"Error: {config.MANUAL_PATH} not found")
        return

    pdf_files = glob.glob(os.path.join(config.MANUAL_PATH, "**/*.pdf"), recursive=True)
    documents = []
    
    print(f"Found {len(pdf_files)} PDFs. Processing images and tables...")
    for file_path in pdf_files:
        docs = process_pdf(file_path)
        documents.extend(docs)
        
    print(f"Successfully loaded {len(documents)} pages with enriched context")

    # split into chunks
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000, # using 1000 chars to keep the context
        chunk_overlap=150, # 150 chars overlap to not cut sentences (keep context)
        separators=["\n\n", "\n", ".", " ", ""]
    )
    chunks = text_splitter.split_documents(documents)
    print(f"Document split into {len(chunks)} chunks")

    # embedding model
    embeddings = get_embeddings()

    # vector db
    vector_db = Chroma(persist_directory=config.DB_DIR, embedding_function=embeddings)
    chunk_ids = []
    for i, chunk in enumerate(chunks):
        chunk_id = f"{chunk.metadata['source']}_{chunk.metadata['page']}_{i}"
        chunk_ids.append(chunk_id)
    
    vector_db.add_documents(chunks, ids=chunk_ids)
    
    print(f"Database created successfully in folder: {config.DB_DIR}")