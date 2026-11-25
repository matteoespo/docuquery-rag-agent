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
        assert events == [
            {"type": "sources", "sources": []},
            {"type": "token", "text": "36 V "},
            {"type": "token", "text": "DC"},
            {"type": "done"},
        ]
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


def _node(event, name, output=None):
    e = {"event": event, "name": name, "tags": [], "metadata": {"langgraph_node": name}}
    if output is not None:
        e["data"] = {"output": output}
    return e


class TestStreamingStatusAndSources:
    """status events while nodes run; sources (deduplicated) before the answer tokens."""

    def _events(self, agent_events, chat_history=()):
        from langchain_core.messages import AIMessageChunk

        from backend.api.routers import generate_tokens

        class FakeAgent:
            async def astream_events(self, state, **kwargs):
                for e in agent_events:
                    yield e
                yield {"event": "on_chat_model_start", "tags": ["generate_node"]}
                yield {"event": "on_chat_model_stream", "tags": ["generate_node"],
                       "data": {"chunk": AIMessageChunk(content="2.4 m/s")}}

        async def collect():
            state = {"query": "q", "chat_history": list(chat_history)}
            return [json.loads(line[len("data: "):]) async for line in generate_tokens(FakeAgent(), state)]

        return asyncio.run(collect())

    def test_status_then_sources_then_tokens(self):
        docs = [
            Document(page_content="a", metadata={"source": "data/pdfs/kx200.pdf", "page": 2}),
            Document(page_content="b", metadata={"source": "data/pdfs/kx200.pdf", "page": 2}),
            Document(page_content="c", metadata={"source": "https://example.org/kx", "page": "web"}),
        ]
        events = self._events([
            _node("on_chain_start", "contextualize"),
            _node("on_chain_start", "retrieve"),
            # a runnable inside the node must not produce its own status
            {"event": "on_chain_start", "name": "RunnableSequence", "metadata": {"langgraph_node": "retrieve"}},
            _node("on_chain_end", "retrieve", {"documents": docs}),
            _node("on_chain_start", "generate"),
        ])
        assert events == [
            {"type": "status", "text": "Searching your documents..."},
            {"type": "status", "text": "Writing the answer..."},
            {"type": "sources", "sources": [
                {"source": "kx200.pdf", "page": 2, "url": None},
                {"source": "https://example.org/kx", "page": None, "url": "https://example.org/kx"},
            ]},
            {"type": "token", "text": "2.4 m/s"},
            {"type": "done"},
        ]

    def test_followup_rewrite_status_only_with_history(self):
        events = self._events([_node("on_chain_start", "contextualize")],
                              chat_history=[{"role": "user", "content": "hi"}])
        assert events[0] == {"type": "status", "text": "Understanding your follow-up question..."}


class TestDocumentFileEndpoint:
    def _client(self, tmp_path, monkeypatch):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient

        import api.routers as routers

        monkeypatch.setattr(routers.settings, "manual_path", str(tmp_path))
        app = FastAPI()
        app.include_router(routers.router)
        return TestClient(app)

    def test_serves_pdf_inline(self, tmp_path, monkeypatch):
        (tmp_path / "A Review for  Testing.pdf").write_bytes(b"%PDF-1.4 test")
        resp = self._client(tmp_path, monkeypatch).get("/api/documents/A Review for  Testing.pdf/file")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.headers["content-disposition"].startswith("inline")
        assert resp.content == b"%PDF-1.4 test"

    def test_missing_non_pdf_and_traversal_are_rejected(self, tmp_path, monkeypatch):
        (tmp_path / "notes.txt").write_text("secret")
        client = self._client(tmp_path, monkeypatch)
        assert client.get("/api/documents/missing.pdf/file").status_code == 404
        assert client.get("/api/documents/notes.txt/file").status_code == 404
        assert client.get("/api/documents/..secret.pdf/file").status_code == 400
