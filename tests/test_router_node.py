"""Router node: routing must be deterministic in CI without a live Ollama server."""
from unittest.mock import MagicMock, patch

from backend.ai.rag_engine import router as router_node


@patch("backend.ai.rag_engine.ChatPromptTemplate.from_messages")
@patch("backend.ai.rag_engine.llm")
def test_router_routes_technical_to_vector_store(mock_llm, mock_from_messages):
    mock_structured = MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured

    mock_prompt = MagicMock()
    mock_chain = MagicMock()
    mock_chain.invoke.return_value = MagicMock(datasource="vector_store")
    mock_prompt.__or__.return_value = mock_chain
    mock_from_messages.return_value = mock_prompt

    state = {"query": "How do I reset my router to factory settings?"}
    assert router_node(state) == "vector_store"


@patch("backend.ai.rag_engine.ChatPromptTemplate.from_messages")
@patch("backend.ai.rag_engine.llm")
def test_router_routes_general_to_out_of_scope(mock_llm, mock_from_messages):
    mock_structured = MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured

    mock_prompt = MagicMock()
    mock_chain = MagicMock()
    mock_chain.invoke.return_value = MagicMock(datasource="out_of_scope")
    mock_prompt.__or__.return_value = mock_chain
    mock_from_messages.return_value = mock_prompt

    state = {"query": "Hello! Can you tell me what 100 divided by 4 is?"}
    assert router_node(state) == "out_of_scope"
