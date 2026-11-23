"""Follow-up question rewriting, grounded grading, web search dedup, and answer reset streaming."""

import asyncio
import json
from unittest.mock import MagicMock, patch

from langchain_core.documents import Document
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.outputs import ChatGeneration, ChatResult

from backend.ai.nodes.contextualize import contextualize
from backend.ai.nodes.generation import grade_answer
from backend.ai.nodes.websearch import websearch
from backend.api.routers import generate_tokens

HISTORY = [
    {"role": "user", "content": "Tell me about the X100 pump."},
    {"role": "assistant", "content": "The X100 is a centrifugal pump."},
]
REWRITE = "What is the input voltage of the X100 pump?"


class ScriptedChatModel(BaseChatModel):
    """Answers according to which node is calling, recognised by its system prompt."""

    calls: list = []
    grader_says: str = "yes"

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        system = messages[0].content
        human = messages[-1].content
        self.calls.append((system, human))
        if "standalone question" in system:
            reply = REWRITE
        elif "strict routing system" in system:
            reply = "vector_store"
        elif "relevance of retrieved documents" in system:
            reply = "vector_store"
        elif "grader assessing whether an answer" in system:
            reply = self.grader_says
        else:
            reply = "It needs 24V [Source: x100.pdf, Page: 2]"
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=reply))])

    def calls_matching(self, text: str) -> list:
        return [c for c in self.calls if text in c[0]]


# Contextualize

def test_contextualize_without_history_skips_llm():
    with patch("backend.ai.nodes.contextualize.get_llm") as get_llm:
        out = asyncio.run(contextualize({"query": "What is the X100?", "chat_history": []}))
    assert out == {"search_query": "What is the X100?"}
    get_llm.assert_not_called()


def test_contextualize_rewrites_followup_using_history():
    llm = ScriptedChatModel(calls=[])
    with patch("backend.ai.nodes.contextualize.get_llm", return_value=llm):
        out = asyncio.run(contextualize({"query": "what about its voltage?", "chat_history": HISTORY}))
    assert out == {"search_query": REWRITE}
    _, human = llm.calls[0]
    assert "X100 pump" in human and "what about its voltage?" in human


def test_contextualize_falls_back_to_query_on_llm_error():
    broken = MagicMock()
    broken.side_effect = RuntimeError("ollama down")
    with patch("backend.ai.nodes.contextualize.get_llm", return_value=broken):
        out = asyncio.run(contextualize({"query": "what about it?", "chat_history": HISTORY}))
    assert out == {"search_query": "what about it?"}


# Grader

def test_grader_sees_the_documents():
    llm = ScriptedChatModel(calls=[], grader_says="no")
    state = {
        "query": "Input voltage?",
        "answer": "48V",
        "retries": 0,
        "documents": [Document(page_content="Input: 24V DC", metadata={"source": "data/pdfs/x100.pdf", "page": 2})],
    }
    with patch("backend.ai.nodes.generation.get_llm", return_value=llm):
        assert grade_answer(state) == "not_useful"
    _, human = llm.calls[0]
    assert "Input: 24V DC" in human
    assert "[Source: x100.pdf, Page: 2]" in human


# Web search

def _ddgs_returning(results):
    ddgs = MagicMock()
    ddgs.return_value.text.return_value = results
    return ddgs


def test_websearch_dedupes_and_does_not_mutate_state():
    existing = [Document(page_content="a", metadata={"source": "https://a.com", "page": "web"})]
    state = {"query": "raw", "search_query": REWRITE, "documents": existing}
    results = [{"href": "https://a.com", "body": "a"}, {"href": "https://b.com", "body": "b"}]

    with patch("backend.ai.nodes.websearch.DDGS", _ddgs_returning(results)) as ddgs:
        out = websearch(state)

    ddgs.return_value.text.assert_called_once_with(REWRITE, max_results=5)
    assert [d.metadata["source"] for d in out["documents"]] == ["https://a.com", "https://b.com"]
    assert len(existing) == 1


def test_websearch_failure_adds_no_placeholder_document():
    ddgs = MagicMock()
    ddgs.return_value.text.side_effect = RuntimeError("rate limited")
    with patch("backend.ai.nodes.websearch.DDGS", ddgs):
        out = websearch({"query": "q", "documents": []})
    assert out == {"documents": [], "retries": 1}


# Streaming

class FakeAgent:
    def __init__(self, events):
        self.events = events

    async def astream_events(self, *args, **kwargs):
        for event in self.events:
            yield event


def test_stream_resets_client_when_answer_is_regenerated():
    start = {"event": "on_chat_model_start", "tags": ["generate_node"]}

    def token(text):
        return {"event": "on_chat_model_stream", "tags": ["generate_node"],
                "data": {"chunk": AIMessageChunk(content=text)}}

    agent = FakeAgent([start, token("bad answer"), start, token("good answer")])

    async def collect():
        return [json.loads(line[len("data: "):]) async for line in generate_tokens(agent, {})]

    assert asyncio.run(collect()) == [
        {"token": "bad answer"},
        {"reset": True, "status": "Searching the web for more information..."},
        {"token": "good answer"},
        {"token": "[stream completed]"},
    ]


# Full graph

def test_graph_retrieves_with_rewritten_followup():
    from ai.agent import load_agent

    llm = ScriptedChatModel(calls=[])
    vector_db = MagicMock()
    vector_db.similarity_search.return_value = [
        Document(page_content="X100 input: 24V DC", metadata={"source": "data/pdfs/x100.pdf", "page": 2}),
    ]
    targets = ["ai.nodes.contextualize", "ai.nodes.routing", "ai.nodes.retrieval", "ai.nodes.generation", "ai.memory"]
    patches = [patch(f"{t}.get_llm", return_value=llm) for t in targets]
    patches.append(patch("ai.nodes.retrieval.Chroma", return_value=vector_db))
    for p in patches:
        p.start()
    try:
        result = asyncio.run(load_agent().ainvoke({
            "query": "what about its voltage?",
            "documents": [], "answer": "", "chat_history": HISTORY, "retries": 0,
        }))
    finally:
        for p in patches:
            p.stop()

    vector_db.similarity_search.assert_called_once()
    assert vector_db.similarity_search.call_args[0][0] == REWRITE
    assert REWRITE in llm.calls_matching("strict routing system")[0][1]
    assert result["search_query"] == REWRITE
    assert result["answer"] == "It needs 24V [Source: x100.pdf, Page: 2]"
    # The original wording is what gets answered.
    generation_human = [c[1] for c in llm.calls if "technical assistant" in c[0]]
    assert generation_human == ["what about its voltage?"]
