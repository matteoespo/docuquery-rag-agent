"""Unit tests for RAG graph nodes that avoid real vector DB or Ollama where possible."""
from unittest.mock import MagicMock, patch

from langchain_core.documents import Document

from backend.ai.rag_engine import check_if_more_info_needed, generate, out_of_scope_node


def test_out_of_scope_node_message():
    result = out_of_scope_node({"query": "any"})
    assert "answer" in result
    assert "technical assistant" in result["answer"].lower()
    assert "manual" in result["answer"].lower()


def test_check_if_more_info_needed_no_documents():
    state = {"query": "What is the torque spec?", "documents": []}
    assert check_if_more_info_needed(state) == "more_info_needed"


@patch("backend.ai.rag_engine.ChatPromptTemplate.from_messages")
@patch("backend.ai.rag_engine.llm")
def test_check_if_more_info_needed_with_docs_routes_vector_store(mock_llm, mock_from_messages):
    mock_structured = MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured

    mock_prompt = MagicMock()
    mock_chain = MagicMock()
    mock_chain.invoke.return_value = MagicMock(datasource="vector_store")
    mock_prompt.__or__.return_value = mock_chain
    mock_from_messages.return_value = mock_prompt

    docs = [Document(page_content="Torque is 45 Nm for bolt M8.", metadata={})]
    state = {"query": "What is the torque?", "documents": docs}
    assert check_if_more_info_needed(state) == "vector_store"


@patch("backend.ai.rag_engine.ChatPromptTemplate.from_messages")
@patch("backend.ai.rag_engine.llm")
def test_check_if_more_info_needed_with_docs_routes_more_info(mock_llm, mock_from_messages):
    mock_structured = MagicMock()
    mock_llm.with_structured_output.return_value = mock_structured

    mock_prompt = MagicMock()
    mock_chain = MagicMock()
    mock_chain.invoke.return_value = MagicMock(datasource="more_info_needed")
    mock_prompt.__or__.return_value = mock_chain
    mock_from_messages.return_value = mock_prompt

    docs = [Document(page_content="Unrelated boilerplate text.", metadata={})]
    state = {"query": "What is the firmware version?", "documents": docs}
    assert check_if_more_info_needed(state) == "more_info_needed"


@patch("backend.ai.rag_engine.ChatPromptTemplate.from_messages")
@patch("backend.ai.rag_engine.llm")
def test_generate_invokes_chain_with_context(mock_llm, mock_from_messages):
    mock_prompt = MagicMock()
    mock_after_llm = MagicMock()
    mock_chain = MagicMock()
    mock_prompt.__or__.return_value = mock_after_llm
    mock_after_llm.__or__.return_value = mock_chain
    mock_chain.invoke.return_value = "Synthesized answer from context."
    mock_from_messages.return_value = mock_prompt

    docs = [Document(page_content="Spec: 12V DC input.", metadata={"source": "manual"})]
    state = {"query": "What voltage?", "documents": docs, "chat_history": []}
    out = generate(state)

    assert out == {"answer": "Synthesized answer from context."}
    mock_chain.invoke.assert_called_once()
    call_kw = mock_chain.invoke.call_args[0][0]
    assert call_kw["question"] == "What voltage?"
    assert "12V" in call_kw["context"]
    assert "No prior conversation." in call_kw["memory_context"]
