"""Retrieval nodes — vector store search and a relevance gate.

``retrieve`` runs a similarity search and records each chunk's relevance
score (0..1, higher is closer) in its metadata.

``check_if_more_info_needed`` is a conditional edge: if nothing was retrieved
or even the best chunk scores below ``settings.min_relevance``, the agent falls
back to web search. This replaced an LLM "are these documents enough?" call,
which sent most document-answerable questions to the web anyway.
"""

from langchain_chroma import Chroma

from ai.llm import get_embeddings
from ai.state import AgentState, get_search_query
from core.config import settings
from core.logger import get_logger

logger = get_logger(__name__)


def retrieve(state: AgentState):
    """Node: the top ``retrieval_k`` chunks for the (standalone) question."""
    question = get_search_query(state)
    vector_db = Chroma(persist_directory=settings.db_dir, embedding_function=get_embeddings())
    docs = []
    for doc, score in vector_db.similarity_search_with_relevance_scores(question, k=settings.retrieval_k):
        doc.metadata["relevance"] = round(float(score), 3)
        docs.append(doc)
    return {"documents": docs}


def check_if_more_info_needed(state: AgentState):
    """Conditional edge: "vector_store" if the best chunk is relevant enough, else "more_info_needed"."""
    docs = state.get("documents", [])
    if not docs:
        return "more_info_needed"
    best = max(doc.metadata.get("relevance", 0.0) for doc in docs)
    if best < settings.min_relevance:
        logger.info("Best chunk relevance %.3f < %.3f: falling back to web search", best, settings.min_relevance)
        return "more_info_needed"
    return "vector_store"
