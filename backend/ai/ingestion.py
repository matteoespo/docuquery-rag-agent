import os
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader, DirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
import core.config as config
from ai.llm import get_embeddings

load_dotenv()

def ingest_manual():
    """
    Loads a PDF, splits it into chunks and stores embeddings in a local chromadb
    """

    # load the directory of manuals
    if not os.path.exists(config.MANUAL_PATH):
        print(f"Error: {config.MANUAL_PATH} not found")
        return

    # loads all documents in the directory
    loader = DirectoryLoader(config.MANUAL_PATH, glob="**/*.pdf", loader_cls=PyPDFLoader)
    documents = loader.load()
    print(f"Successfully loaded {len(documents)} pages")

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