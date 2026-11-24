"""Tests for token streaming functionality via FastAPI SSE and LangGraph astream_events."""
import json
from unittest.mock import AsyncMock, MagicMock, patch, call
import asyncio
import pytest
from langchain_core.documents import Document

from backend.ai.state import AgentState
from backend.api.routers import generate_tokens


class TestStreamingPromptStructure:
    """Test that new prompt structure supports KV cache hits."""

    @patch("backend.ai.nodes.generation.ChatPromptTemplate.from_messages")
    @patch("backend.ai.nodes.generation.get_llm")
    def test_generate_static_prefix_first(self, mock_get_llm, mock_from_messages):
        mock_llm = mock_get_llm.return_value
        """Verify static content (system + context) comes before dynamic query."""
        from backend.ai.nodes.generation import generate

        mock_prompt = MagicMock()
        mock_after_llm = MagicMock()
        mock_chain = MagicMock()
        mock_prompt.__or__.return_value = mock_after_llm
        mock_after_llm.__or__.return_value = mock_chain
        mock_chain.ainvoke = AsyncMock(return_value="Test answer")
        mock_from_messages.return_value = mock_prompt

        docs = [Document(page_content="Static doc content", metadata={})]
        state = {
            "query": "What is X?",
            "documents": docs,
            "chat_history": [],
        }

        asyncio.run(generate(state, config=MagicMock()))

        # Verify ChatPromptTemplate.from_messages was called
        assert mock_from_messages.called
        call_args = mock_from_messages.call_args[0][0]

        # Expected structure: [("system", static_prefix), ("human", "{question}")]
        assert len(call_args) == 2
        assert call_args[0][0] == "system"
        assert call_args[1][0] == "human"
        assert "{question}" in call_args[1][1]

        # Verify ainvoke gets only {question}, not context/memory_context
        mock_chain.ainvoke.assert_called_once()
        invoke_args = mock_chain.ainvoke.call_args[0][0]
        assert invoke_args == {"question": "What is X?"}
    @patch("backend.ai.nodes.generation.ChatPromptTemplate.from_messages")
    @patch("backend.ai.nodes.generation.get_llm")
    def test_generate_static_prefix_contains_system_and_context(
        self, mock_get_llm, mock_from_messages
    ):
        mock_llm = mock_get_llm.return_value
        """Verify static prefix contains system instructions + context + memory."""
        from backend.ai.nodes.generation import generate

        mock_prompt = MagicMock()
        mock_after_llm = MagicMock()
        mock_chain = MagicMock()
        mock_prompt.__or__.return_value = mock_after_llm
        mock_after_llm.__or__.return_value = mock_chain
        mock_chain.ainvoke = AsyncMock(return_value="Answer")
        mock_from_messages.return_value = mock_prompt

        docs = [Document(page_content="Critical spec: 48V", metadata={})]
        state = {
            "query": "Voltage?",
            "documents": docs,
            "chat_history": [
                {"role": "user", "content": "Previous question"},
                {"role": "assistant", "content": "Previous answer"},
            ],
        }

        asyncio.run(generate(state, config=MagicMock()))
        call_args = mock_from_messages.call_args[0][0]
        system_msg = call_args[0][1]

        assert "technical assistant" in system_msg
        assert "RETRIEVED CONTEXT:" in system_msg
        assert "Critical spec: 48V" in system_msg
        assert "CONVERSATION MEMORY:" in system_msg

    @patch("backend.ai.nodes.generation.get_llm")
    def test_generate_kv_cache_prefix_reuse(self, mock_get_llm):
        """Same documents + different questions -> byte-identical system prompt."""
        from backend.ai.nodes.generation import generate

        docs = [
            Document(page_content="Doc A content", metadata={"source": "manual1.pdf", "page": 1}),
            Document(page_content="Doc B content", metadata={"source": "manual2.pdf", "page": 3}),
        ]
        prompts = []

        def capture(messages):
            prompts.append(messages)
            chain = MagicMock()
            chain.ainvoke = AsyncMock(return_value="answer")
            prompt = MagicMock()
            prompt.__or__.return_value.__or__.return_value = chain
            return prompt

        with patch("backend.ai.nodes.generation.ChatPromptTemplate.from_messages", side_effect=capture):
            for query in ("Query 1", "A completely different question"):
                asyncio.run(generate({"query": query, "documents": docs, "chat_history": []}, config=MagicMock()))

        assert prompts[0][0][1] == prompts[1][0][1]
        assert "Query 1" not in prompts[0][0][1]
        assert prompts[0][1] == ("human", "{question}")


class TestStreamingEndpoint:
    """Real HTTP request to /api/chat/stream with a fake agent."""

    def test_chat_stream_endpoint(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from langchain_core.messages import AIMessageChunk
        import api.routers as routers

        received = {}

        class FakeAgent:
            async def astream_events(self, state, **kwargs):
                received.update(state)
                yield {"event": "on_chat_model_start", "tags": ["generate_node"]}
                for text in ("36 V ", "DC"):
                    yield {"event": "on_chat_model_stream", "tags": ["generate_node"],
                           "data": {"chunk": AIMessageChunk(content=text)}}

        app = FastAPI()
        app.include_router(routers.router)
        app.state.agent = FakeAgent()
        history = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "hello"}]

        resp = TestClient(app).post("/api/chat/stream", json={"query": "Input voltage?", "chat_history": history})

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        assert resp.headers["cache-control"] == "no-cache"
        events = [json.loads(line[len("data: "):]) for line in resp.text.splitlines() if line.startswith("data: ")]
        assert events == [{"token": "36 V "}, {"token": "DC"}, {"token": "[stream completed]"}]
        assert received["query"] == "Input voltage?"
        assert received["chat_history"] == history
        assert received["retries"] == 0


class TestStreamingLLMConfig:
    """Test LLM initialization with streaming settings."""

    @patch("backend.ai.llm.settings")
    def test_get_llm_keep_alive_infinite(self, mock_settings):
        """Verify keep_alive=-1 prevents model unload."""
        from backend.ai.llm import get_llm

        mock_settings.llm_model = "llama3.2:3b"
        mock_settings.ollama_base_url = "http://ollama:11434"

        with patch("backend.ai.llm.ChatOllama") as mock_chat_ollama:
            get_llm.cache_clear()
            get_llm()

            call_kwargs = mock_chat_ollama.call_args[1]
            assert call_kwargs.get("keep_alive") == -1

    @patch("backend.ai.llm.settings")
    def test_get_llm_fixed_num_ctx(self, mock_settings):
        """Verify num_ctx=8192 for consistent context window."""
        from backend.ai.llm import get_llm

        mock_settings.llm_model = "llama3.2:3b"
        mock_settings.ollama_base_url = "http://ollama:11434"

        with patch("backend.ai.llm.ChatOllama") as mock_chat_ollama:
            get_llm.cache_clear()
            get_llm()

            call_kwargs = mock_chat_ollama.call_args[1]
            assert call_kwargs.get("num_ctx") == 8192
