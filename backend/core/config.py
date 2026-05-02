'''
Loads environment variables
'''
import os

DB_DIR = "data/chroma_db"
MANUAL_PATH = "data/pdfs/"
EMBEDDING_MODEL = "nomic-embed-text"
LLM_MODEL = "llama3.1"
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
