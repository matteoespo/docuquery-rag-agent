"""Tests for token streaming functionality via FastAPI SSE and LangGraph astream_events."""
import asyncio
import json
from unittest.mock import MagicMock, patch

from langchain_core.documents import Document


class TestStreamingPromptStructure:
    """Prompt layout: static system prompt (KV-cache friendly), history as messages, docs in the user turn."""

    def _messages(self, query, documents, chat_history=()):
        from backend.ai.nodes.generation import generate
        from tests.fakes import ScriptedChatModel

        llm = ScriptedChatModel()
        state = {"query": query, "documents": documents, "chat_history": list(chat_history)}
        with patch("backend.ai.nodes.generation.get_llm", return_value=llm):
            asyncio.run(generate(state, config=MagicMock()))
        return llm.calls[0]

    def test_generate_kv_cache_prefix_reuse(self):
        """Different documents and questions -> byte-identical system prompt."""
        first = self._messages("Query 1", [Document(page_content="Doc A", metadata={"source": "a.pdf", "page": 1})])
        second = self._messages("Another question", [Document(page_content="Doc B", metadata={"source": "b.pdf", "page": 7})])
        assert first[0].content == second[0].content
        assert "Doc A" not in first[0].content and "Query 1" not in first[0].content

    def test_history_is_sent_as_chat_messages(self):
        history = [{"role": "user", "content": "What is the KX-200?"},
                   {"role": "assistant", "content": "A conveyor controller."}]
        messages = self._messages("Its max speed?", [], history)

        assert [m.type for m in messages] == ["system", "human", "ai", "human"]
        assert messages[1].content == "What is the KX-200?"
        assert "CONVERSATION MEMORY" not in "".join(m.content for m in messages)

    def test_braces_in_documents_do_not_break_generation(self):
        """Document text used to be formatted as a prompt template: '{x}' raised KeyError."""
        docs = [Document(page_content='config = {"speed": 2.4} and {placeholder}', metadata={"source": "a.pdf", "page": 1})]
        messages = self._messages("What is the speed?", docs)
        assert '{"speed": 2.4} and {placeholder}' in messages[-1].content


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
