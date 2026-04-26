from langchain_ollama import OllamaEmbeddings, ChatOllama
import core.config as config

def get_llm():
    """Returns Llama3"""
    return ChatOllama(
        model=config.LLM_MODEL, 
        temperature=0, 
        base_url=config.OLLAMA_BASE_URL
    )

def get_embeddings():
    """Returns the embedding model"""
    return OllamaEmbeddings(
        model=config.EMBEDDING_MODEL, 
        base_url=config.OLLAMA_BASE_URL
    )