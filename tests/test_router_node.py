"""Router node: routing must be deterministic in CI without a live Ollama server."""
from unittest.mock import MagicMock, patch

from backend.ai.nodes.routing import router as router_node


@patch("backend.ai.nodes.routing.ChatPromptTemplate.from_messages")
@patch("backend.ai.nodes.routing.get_llm")
def test_router_routes_technical_to_vector_store(mock_get_llm, mock_from_messages):
    mock_llm = mock_get_llm.return_value
    # Build the mock chain: from_messages() -> | llm -> | StrOutputParser -> .invoke()
    mock_after_llm = MagicMock()
    mock_chain = MagicMock()
    mock_chain.invoke.return_value = 'vector_store'
    mock_after_llm.__or__.return_value = mock_chain  # | StrOutputParser()

    mock_prompt = MagicMock()
    mock_prompt.__or__.return_value = mock_after_llm  # | llm
    mock_from_messages.return_value = mock_prompt

    state = {"query": "How do I reset my router to factory settings?"}
    assert router_node(state) == "vector_store"


@patch("backend.ai.nodes.routing.ChatPromptTemplate.from_messages")
@patch("backend.ai.nodes.routing.get_llm")
def test_router_routes_general_to_out_of_scope(mock_get_llm, mock_from_messages):
    mock_llm = mock_get_llm.return_value
    # Build the mock chain: from_messages() -> | llm -> | StrOutputParser -> .invoke()
    mock_after_llm = MagicMock()
    mock_chain = MagicMock()
    mock_chain.invoke.return_value = 'out_of_scope'
    mock_after_llm.__or__.return_value = mock_chain  # | StrOutputParser()

    mock_prompt = MagicMock()
    mock_prompt.__or__.return_value = mock_after_llm  # | llm
    mock_from_messages.return_value = mock_prompt

    state = {"query": "Hello! Can you tell me what 100 divided by 4 is?"}
    assert router_node(state) == "out_of_scope"
