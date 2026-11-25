"""Graph nodes without a real vector DB or Ollama."""

import asyncio
from unittest.mock import MagicMock, patch

from langchain_core.documents import Document

from backend.ai.nodes.generation import generate
from backend.ai.nodes.retrieval import check_if_more_info_needed, retrieve
from backend.ai.nodes.routing import out_of_scope_node
from tests.fakes import ScriptedChatModel


def doc(text="Torque is 45 Nm.", relevance=0.6, source="data/pdfs/manual.pdf", page=1):
    return Document(page_content=text, metadata={"source": source, "page": page, "relevance": relevance})


def test_out_of_scope_node_message():
    result = out_of_scope_node({"query": "any"})
    assert "technical assistant" in result["answer"].lower()


# Relevance gate

def test_no_documents_needs_more_info():
    assert check_if_more_info_needed({"query": "q", "documents": []}) == "more_info_needed"


def test_relevant_documents_are_used_without_an_llm_call(monkeypatch):
    import backend.ai.nodes.retrieval as retrieval

    monkeypatch.setattr(retrieval.settings, "min_relevance", 0.33)
    docs = [doc(relevance=0.2), doc(relevance=0.55)]
    assert check_if_more_info_needed({"query": "q", "documents": docs}) == "vector_store"


def test_irrelevant_documents_fall_back_to_web(monkeypatch):
    import backend.ai.nodes.retrieval as retrieval

    monkeypatch.setattr(retrieval.settings, "min_relevance", 0.33)
    docs = [doc(relevance=0.28), doc(relevance=0.3)]
    assert check_if_more_info_needed({"query": "q", "documents": docs}) == "more_info_needed"


def test_retrieve_records_relevance_and_uses_standalone_query():
    vector_db = MagicMock()
    vector_db.similarity_search_with_relevance_scores.return_value = [(doc(relevance=None), 0.61234)]
    with patch("backend.ai.nodes.retrieval.Chroma", return_value=vector_db):
        out = retrieve({"query": "its voltage?", "search_query": "Q7 input voltage?"})

    assert vector_db.similarity_search_with_relevance_scores.call_args[0][0] == "Q7 input voltage?"
    assert out["documents"][0].metadata["relevance"] == 0.612


# Generation

def test_generate_answers_from_documents_in_the_user_turn():
    llm = ScriptedChatModel(default="12V [Source: manual.pdf, Page: 4]")
    state = {"query": "What voltage?", "documents": [doc("Spec: 12V DC input.", page=4)], "chat_history": []}

    with patch("backend.ai.nodes.generation.get_llm", return_value=llm):
        out = asyncio.run(generate(state, config=MagicMock()))

    assert out == {"answer": "12V [Source: manual.pdf, Page: 4]"}
    system, human = llm.calls[0]
    assert "Spec: 12V DC" not in system.content
    assert "[Source: manual.pdf, Page: 4]\nSpec: 12V DC input." in human.content
    assert human.content.endswith("Question: What voltage?")
