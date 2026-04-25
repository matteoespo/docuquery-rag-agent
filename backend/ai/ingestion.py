import os
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
import core.config as config
from ai.llm import get_embeddings


def ingest_manual():
    """
    Loads a PDF, splits it into chunks and stores embeddings in a local chromadb
    """

    # load the PDF document
    if not os.path.exists(config.MANUAL_PATH):
        print(f"Error: {config.MANUAL_PATH} not found")
        return

    loader = PyPDFLoader(config.MANUAL_PATH)
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
    vector_db = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=config.DB_DIR
    )
    
    print(f"Database created successfully in folder: {config.DB_DIR}")