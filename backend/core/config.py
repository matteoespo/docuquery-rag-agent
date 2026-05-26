'''
Loads environment variables
'''
import os

DB_DIR = "data/chroma_db"
MANUAL_PATH = "data/pdfs/"
EMBEDDING_MODEL = "nomic-embed-text"
LLM_MODEL = "llama3.2:3b"
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")

# Ingestion tuning
SKIP_IMAGE_CAPTIONING = os.getenv("SKIP_IMAGE_CAPTIONING", "false").lower() == "true"
MIN_IMAGE_BYTES = int(os.getenv("MIN_IMAGE_BYTES", "5000"))
MIN_IMAGE_DIMENSION = int(os.getenv("MIN_IMAGE_DIMENSION", "100"))
MAX_VISION_WORKERS = int(os.getenv("MAX_VISION_WORKERS", "2"))
MAX_PDF_WORKERS = int(os.getenv("MAX_PDF_WORKERS", "4"))
CHROMA_BATCH_SIZE = int(os.getenv("CHROMA_BATCH_SIZE", "100"))
