"""Router: structured output, prefers answering, shows document names, never hides LLM errors."""

from unittest.mock import patch

import pytest
from langchain_core.exceptions import OutputParserException

from backend.ai.nodes.routing import router
from tests.fakes import ScriptedChatModel


def _route(llm, query="How do I calibrate the sensor?"):
    with patch("backend.ai.nodes.routing.get_llm", return_value=llm):
        return router({"query": query})


def test_routes_document_questions_to_vector_store():
    assert _route(ScriptedChatModel(route="vector_store")) == "vector_store"


def test_routes_small_talk_out_of_scope():
    assert _route(ScriptedChatModel(route="out_of_scope"), "hi, how are you?") == "out_of_scope"


def test_unparseable_output_tries_to_answer():
    llm = ScriptedChatModel(route_error=OutputParserException("not json"))
    assert _route(llm) == "vector_store"


def test_llm_failure_is_not_disguised_as_out_of_scope():
    with pytest.raises(ConnectionError):
        _route(ScriptedChatModel(route_error=ConnectionError("ollama unreachable")))


def test_router_sees_uploaded_document_names_and_standalone_query(tmp_path, monkeypatch):
    import backend.ai.nodes.routing as routing

    (tmp_path / "Ontology review.pdf").write_bytes(b"%PDF-1.4")
    monkeypatch.setattr(routing.settings, "manual_path", str(tmp_path))
    llm = ScriptedChatModel()

    with patch("backend.ai.nodes.routing.get_llm", return_value=llm):
        router({"query": "who wrote it?", "search_query": "Who wrote the ontology review?"})

    system, human = llm.calls[0]
    assert "- Ontology review" in system.content
    assert "When in doubt" in system.content
    assert human.content == "Who wrote the ontology review?"
