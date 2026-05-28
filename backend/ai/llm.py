"""LLM and embedding provider factories.

Centralises creation of Ollama-backed models. Uses ``lru_cache`` so that
repeated calls across modules return the same client instance.
"""

from functools import lru_cache

from langchain_ollama import ChatOllama, OllamaEmbeddings

from core.config import settings


@lru_cache
def get_llm() -> ChatOllama:
    """Return the main chat LLM (cached singleton)."""
    return ChatOllama(
        model=settings.llm_model,
        temperature=0,
        base_url=settings.ollama_base_url,
        streaming=True,
        keep_alive=-1,
        num_ctx=8192,
    )


@lru_cache
def get_embeddings() -> OllamaEmbeddings:
    """Return the embedding model (cached singleton)."""
    return OllamaEmbeddings(
        model=settings.embedding_model,
        base_url=settings.ollama_base_url,
    )


@lru_cache
def get_vision_llm() -> ChatOllama:
    """Return the vision LLM for image captioning (cached singleton)."""
    return ChatOllama(
        model=settings.vision_model,
        temperature=0,
        base_url=settings.ollama_base_url,
        streaming=True,
        keep_alive=-1,
        num_ctx=8192,
    )