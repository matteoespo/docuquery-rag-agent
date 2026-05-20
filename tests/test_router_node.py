"""Router node: routing must be deterministic in CI without a live Ollama server."""
from unittest.mock import MagicMock, patch

from backend.ai.nodes.routing import router as router_node


@patch("backend.ai.nodes.routing.ChatPromptTemplate.from_messages")
@patch("backend.ai.nodes.routing.llm")
def test_router_routes_technical_to_vector_store(mock_llm, mock_from_messages):
    # Build the mock chain: from_messages() -> .partial() -> | llm -> | StrOutputParser -> .invoke()
    mock_prompt_partial = MagicMock()
    mock_after_llm = MagicMock()
    mock_chain = MagicMock()
    mock_chain.invoke.return_value = '{"datasource": "vector_store"}'
    mock_after_llm.__or__.return_value = mock_chain  # | StrOutputParser()
    mock_prompt_partial.__or__.return_value = mock_after_llm  # | llm

    mock_prompt = MagicMock()
    mock_prompt.partial.return_value = mock_prompt_partial
    mock_from_messages.return_value = mock_prompt

    state = {"query": "How do I reset my router to factory settings?"}
    assert router_node(state) == "vector_store"


@patch("backend.ai.nodes.routing.ChatPromptTemplate.from_messages")
@patch("backend.ai.nodes.routing.llm")
def test_router_routes_general_to_out_of_scope(mock_llm, mock_from_messages):
    # Build the mock chain: from_messages() -> .partial() -> | llm -> | StrOutputParser -> .invoke()
    mock_prompt_partial = MagicMock()
    mock_after_llm = MagicMock()
    mock_chain = MagicMock()
    mock_chain.invoke.return_value = '{"datasource": "out_of_scope"}'
    mock_after_llm.__or__.return_value = mock_chain  # | StrOutputParser()
    mock_prompt_partial.__or__.return_value = mock_after_llm  # | llm

    mock_prompt = MagicMock()
    mock_prompt.partial.return_value = mock_prompt_partial
    mock_from_messages.return_value = mock_prompt

    state = {"query": "Hello! Can you tell me what 100 divided by 4 is?"}
    assert router_node(state) == "out_of_scope"
