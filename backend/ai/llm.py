"""LLM and embedding provider factories.

Centralises creation of Ollama-backed models. Uses ``lru_cache`` so that
repeated calls across modules return the same client instance.

Token streaming needs no flag: LangChain streams automatically when the
caller listens for stream events (``astream_events`` in the chat endpoint).
"""

from functools import lru_cache

from langchain_core.embeddings import Embeddings
from langchain_ollama import ChatOllama, OllamaEmbeddings

from core.config import settings


@lru_cache
def get_llm() -> ChatOllama:
    """Return the main chat LLM (cached singleton)."""
    return ChatOllama(
        model=settings.llm_model,
        temperature=0,
        base_url=settings.ollama_base_url,
        keep_alive=-1,
        num_ctx=8192,
    )


class PrefixedEmbeddings(Embeddings):
    """Adds task prefixes to the text being embedded (the stored text is unchanged).

    nomic-embed-text was trained with "search_query: " / "search_document: "
    prefixes and retrieves noticeably worse without them.
    """

    def __init__(self, base: Embeddings, query_prefix: str, document_prefix: str):
        self.base = base
        self.query_prefix = query_prefix
        self.document_prefix = document_prefix

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.base.embed_documents([self.document_prefix + t for t in texts])

    def embed_query(self, text: str) -> list[float]:
        return self.base.embed_query(self.query_prefix + text)

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return await self.base.aembed_documents([self.document_prefix + t for t in texts])

    async def aembed_query(self, text: str) -> list[float]:
        return await self.base.aembed_query(self.query_prefix + text)


# Task prefixes per embedding model family (matched by model-name prefix).
EMBEDDING_PREFIXES = {
    "nomic-embed-text": ("search_query: ", "search_document: "),
}


@lru_cache
def get_embeddings() -> Embeddings:
    """Return the embedding model (cached singleton), with task prefixes if it needs them."""
    base = OllamaEmbeddings(
        model=settings.embedding_model,
        base_url=settings.ollama_base_url,
        num_gpu=settings.embedding_num_gpu,
    )
    for family, (query_prefix, document_prefix) in EMBEDDING_PREFIXES.items():
        if settings.embedding_model.startswith(family):
            return PrefixedEmbeddings(base, query_prefix, document_prefix)
    return base


@lru_cache
def get_vision_llm() -> ChatOllama:
    """Return the vision LLM for image captioning (cached singleton)."""
    return ChatOllama(
        model=settings.vision_model,
        temperature=0,
        base_url=settings.ollama_base_url,
        keep_alive=-1,
        num_ctx=8192,
    )