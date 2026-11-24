"""Follow-up question rewriting, grounded grading, web search dedup, and answer reset streaming."""

import asyncio
import json
from unittest.mock import MagicMock, patch

from langchain_core.documents import Document
from langchain_core.messages import AIMessageChunk

from backend.ai.nodes.contextualize import contextualize
from backend.ai.nodes.generation import grade_answer
from backend.ai.nodes.websearch import websearch
from backend.api.routers import generate_tokens
from tests.fakes import ScriptedChatModel

HISTORY = [
    {"role": "user", "content": "Tell me about the X100 pump."},
    {"role": "assistant", "content": "The X100 is a centrifugal pump."},
]
REWRITE = "What is the input voltage of the X100 pump?"


def scripted(grader_says="yes"):
    return ScriptedChatModel(
        replies={"standalone question": REWRITE, "grader assessing whether an answer": grader_says},
        default="It needs 24V [Source: x100.pdf, Page: 2]",
    )


# Contextualize

def test_contextualize_without_history_skips_llm():
    with patch("backend.ai.nodes.contextualize.get_llm") as get_llm:
        out = asyncio.run(contextualize({"query": "What is the X100?", "chat_history": []}))
    assert out == {"search_query": "What is the X100?"}
    get_llm.assert_not_called()


def test_contextualize_rewrites_followup_using_history():
    llm = scripted()
    with patch("backend.ai.nodes.contextualize.get_llm", return_value=llm):
        out = asyncio.run(contextualize({"query": "what about its voltage?", "chat_history": HISTORY}))
    assert out == {"search_query": REWRITE}
    system, human = llm.calls[0]
    assert "X100 pump" in human.content and "what about its voltage?" in human.content
    assert "technical terms" in system.content  # keeps the user's key terms


def test_contextualize_falls_back_to_query_on_llm_error():
    broken = MagicMock()
    broken.side_effect = RuntimeError("ollama down")
    with patch("backend.ai.nodes.contextualize.get_llm", return_value=broken):
        out = asyncio.run(contextualize({"query": "what about it?", "chat_history": HISTORY}))
    assert out == {"search_query": "what about it?"}


# Grader

def test_grader_sees_the_documents():
    llm = scripted(grader_says="no")
    state = {
        "query": "Input voltage?",
        "answer": "48V",
        "retries": 0,
        "documents": [Document(page_content="Input: 24V DC", metadata={"source": "data/pdfs/x100.pdf", "page": 2})],
    }
    with patch("backend.ai.nodes.generation.get_llm", return_value=llm):
        assert grade_answer(state) == "not_useful"
    human = llm.calls[0][-1].content
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

    llm = scripted()
    vector_db = MagicMock()
    vector_db.similarity_search_with_relevance_scores.return_value = [
        (Document(page_content="X100 input: 24V DC", metadata={"source": "data/pdfs/x100.pdf", "page": 2}), 0.7),
    ]
    patches = [patch(f"{t}.get_llm", return_value=llm)
               for t in ("ai.nodes.contextualize", "ai.nodes.routing", "ai.nodes.generation")]
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

    assert vector_db.similarity_search_with_relevance_scores.call_args[0][0] == REWRITE
    router_call = next(m for m in llm.calls if "When in doubt" in m[0].content)
    assert router_call[-1].content == REWRITE
    assert result["search_query"] == REWRITE
    assert result["answer"] == "It needs 24V [Source: x100.pdf, Page: 2]"
    # The original wording is what gets answered, after the prior turns.
    generation = llm.calls_with_system("You are DocuQuery")
    assert len(generation) == 1
    assert [m.type for m in generation[0]] == ["system", "human", "ai", "human"]
    assert generation[0][-1].content.endswith("Question: what about its voltage?")
    # The relevance gate decided on the score alone: rewrite, route, answer, grade.
    assert len(llm.calls) == 4
