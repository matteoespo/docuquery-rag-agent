from langchain_ollama import OllamaEmbeddings, ChatOllama
import core.config as config

def get_llm():
    """Returns Llama3.2 with streaming, persistent KV cache, and fixed context window."""
    return ChatOllama(
        model=config.LLM_MODEL,
        temperature=0,
        base_url=config.OLLAMA_BASE_URL,
        streaming=True,
        keep_alive=-1,
        num_ctx=8192,
    )

def get_embeddings():
    """Returns the embedding model"""
    return OllamaEmbeddings(
        model=config.EMBEDDING_MODEL,
        base_url=config.OLLAMA_BASE_URL,
    )

def get_vision_llm():
    """Returns Moondream for vision tasks"""
    return ChatOllama(
        model="moondream",
        temperature=0,
        base_url=config.OLLAMA_BASE_URL,
        streaming=True,
        keep_alive=-1,
        num_ctx=8192,
    )