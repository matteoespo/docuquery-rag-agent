"""Unit tests for RAG graph nodes that avoid real vector DB or Ollama where possible."""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from langchain_core.documents import Document

from backend.ai.nodes.retrieval import check_if_more_info_needed
from backend.ai.nodes.generation import generate
from backend.ai.nodes.routing import out_of_scope_node


def test_out_of_scope_node_message():
    result = out_of_scope_node({"query": "any"})
    assert "answer" in result
    assert "technical assistant" in result["answer"].lower()
    assert "manual" in result["answer"].lower()


def test_check_if_more_info_needed_no_documents():
    state = {"query": "What is the torque spec?", "documents": []}
    assert check_if_more_info_needed(state) == "more_info_needed"


@patch("backend.ai.nodes.retrieval.ChatPromptTemplate.from_messages")
@patch("backend.ai.nodes.retrieval.llm")
def test_check_if_more_info_needed_with_docs_routes_vector_store(mock_llm, mock_from_messages):
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

    docs = [Document(page_content="Torque is 45 Nm for bolt M8.", metadata={})]
    state = {"query": "What is the torque?", "documents": docs}
    assert check_if_more_info_needed(state) == "vector_store"


@patch("backend.ai.nodes.retrieval.ChatPromptTemplate.from_messages")
@patch("backend.ai.nodes.retrieval.llm")
def test_check_if_more_info_needed_with_docs_routes_more_info(mock_llm, mock_from_messages):
    # Build the mock chain: from_messages() -> .partial() -> | llm -> | StrOutputParser -> .invoke()
    mock_prompt_partial = MagicMock()
    mock_after_llm = MagicMock()
    mock_chain = MagicMock()
    mock_chain.invoke.return_value = '{"datasource": "more_info_needed"}'
    mock_after_llm.__or__.return_value = mock_chain  # | StrOutputParser()
    mock_prompt_partial.__or__.return_value = mock_after_llm  # | llm

    mock_prompt = MagicMock()
    mock_prompt.partial.return_value = mock_prompt_partial
    mock_from_messages.return_value = mock_prompt

    docs = [Document(page_content="Unrelated boilerplate text.", metadata={})]
    state = {"query": "What is the firmware version?", "documents": docs}
    assert check_if_more_info_needed(state) == "more_info_needed"


@patch("backend.ai.nodes.generation.ChatPromptTemplate.from_messages")
@patch("backend.ai.nodes.generation.llm")
def test_generate_invokes_chain_with_context(mock_llm, mock_from_messages):
    mock_prompt = MagicMock()
    mock_after_llm = MagicMock()
    mock_chain = MagicMock()
    
    # Mocking LCEL prompt | llm | output_parser
    mock_prompt.__or__.return_value = mock_after_llm
    mock_after_llm.__or__.return_value = mock_chain
    mock_chain.ainvoke = AsyncMock(return_value="Synthesized answer from context.")
    mock_from_messages.return_value = mock_prompt

    docs = [Document(page_content="Spec: 12V DC input.", metadata={"source": "manual"})]
    state = {"query": "What voltage?", "documents": docs, "chat_history": []}

    # Execute async generate function
    out = asyncio.run(generate(state, config=MagicMock()))
    
    assert out == {"answer": "Synthesized answer from context."}
    mock_chain.ainvoke.assert_called_once()
    
    call_kw = mock_chain.ainvoke.call_args[0][0]
    assert call_kw["question"] == "What voltage?"

    # Verify static prefix contains the retrieved context
    call_messages = mock_from_messages.call_args[0][0]
    system_prompt = call_messages[0][1]
    assert "12V DC input" in system_prompt
    assert "RETRIEVED CONTEXT:" in system_prompt