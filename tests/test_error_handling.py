"""Failures surface as errors instead of being hidden: delete order, chat stream.

Router error handling is tested in test_router_node.py.
"""

import asyncio
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.api.routers import generate_tokens

# Delete endpoint

@pytest.fixture
def delete_client(tmp_path, monkeypatch):
    import api.routers as routers

    monkeypatch.setattr(routers.settings, "manual_path", str(tmp_path))
    app = FastAPI()
    app.include_router(routers.router)
    pdf = tmp_path / "manual.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    return TestClient(app, raise_server_exceptions=False), routers, pdf


def test_delete_keeps_file_when_vector_delete_fails(delete_client, monkeypatch):
    client, routers, pdf = delete_client

    def boom(_):
        raise RuntimeError("chroma unavailable")

    monkeypatch.setattr(routers, "delete_document_vectors", boom)
    assert client.delete("/api/documents/manual.pdf").status_code == 500
    assert pdf.exists(), "file must stay so the delete can be retried"


def test_delete_removes_vectors_then_file(delete_client, monkeypatch):
    client, routers, pdf = delete_client
    calls = []
    monkeypatch.setattr(routers, "delete_document_vectors", lambda path: calls.append((path, pdf.exists())) or 7)

    resp = client.delete("/api/documents/manual.pdf")

    assert resp.status_code == 200
    assert resp.json()["vectors_deleted"] == 7
    assert calls == [(str(pdf), True)]  # vectors deleted while the file still existed
    assert not pdf.exists()


# Chat stream

class FailingAgent:
    async def astream_events(self, *args, **kwargs):
        yield {"event": "on_chain_start", "tags": []}
        raise ConnectionError("ollama unreachable")


def test_stream_reports_agent_failure_as_error_event():
    async def collect():
        return [json.loads(line[len("data: "):]) async for line in generate_tokens(FailingAgent(), {})]

    events = asyncio.run(collect())

    assert len(events) == 1
    assert events[0]["type"] == "error"
    assert "Ollama" in events[0]["message"]


def test_closing_the_stream_stops_the_agent():
    """Stop button: the client disconnects, Starlette closes/cancels the response
    generator, and that must propagate into the agent run (not be swallowed)."""
    state = {"started": False, "closed": False, "finished": False}

    class SlowAgent:
        async def astream_events(self, *args, **kwargs):
            state["started"] = True
            try:
                yield {"event": "on_chain_start", "name": "retrieve", "tags": [],
                       "metadata": {"langgraph_node": "retrieve"}}
                await asyncio.sleep(10)
                state["finished"] = True
                yield {"event": "on_chain_end", "name": "retrieve"}
            finally:
                state["closed"] = True

    async def scenario():
        stream = generate_tokens(SlowAgent(), {})
        first = await stream.__anext__()
        await stream.aclose()  # what Starlette does when the client goes away
        return json.loads(first[len("data: "):])

    first = asyncio.run(asyncio.wait_for(scenario(), timeout=5))
    assert first == {"type": "status", "text": "Searching your documents..."}
    assert state == {"started": True, "closed": True, "finished": False}
