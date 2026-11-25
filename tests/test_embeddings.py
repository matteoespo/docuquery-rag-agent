"""Embedding task prefixes (nomic-embed-text expects search_query / search_document)."""

from unittest.mock import patch

from langchain_core.embeddings import Embeddings

from backend.ai.llm import PrefixedEmbeddings, get_embeddings


class RecordingEmbeddings(Embeddings):
    def __init__(self):
        self.seen = []

    def embed_documents(self, texts):
        self.seen.extend(texts)
        return [[0.0] for _ in texts]

    def embed_query(self, text):
        self.seen.append(text)
        return [0.0]


def test_prefixes_are_added_to_what_gets_embedded():
    base = RecordingEmbeddings()
    emb = PrefixedEmbeddings(base, "search_query: ", "search_document: ")
    emb.embed_documents(["Input voltage: 36 V DC."])
    emb.embed_query("Q7 voltage?")
    assert base.seen == ["search_document: Input voltage: 36 V DC.", "search_query: Q7 voltage?"]


def test_embeddings_run_on_cpu_by_default():
    get_embeddings.cache_clear()
    try:
        emb = get_embeddings()
        assert emb.base.num_gpu == 0
    finally:
        get_embeddings.cache_clear()


def test_only_nomic_models_get_prefixes():
    with patch("backend.ai.llm.settings") as settings:
        settings.ollama_base_url = "http://ollama:11434"
        settings.embedding_num_gpu = 0
        for model, prefixed in (("nomic-embed-text", True), ("nomic-embed-text:v1.5", True), ("mxbai-embed-large", False)):
            settings.embedding_model = model
            get_embeddings.cache_clear()
            assert isinstance(get_embeddings(), PrefixedEmbeddings) is prefixed, model
    get_embeddings.cache_clear()
