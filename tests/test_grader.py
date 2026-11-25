"""Answer grader: off by default; when enabled it can send the agent to web search."""

from unittest.mock import patch

import pytest

import backend.ai.nodes.generation as generation
from backend.ai.nodes.generation import grade_answer
from tests.fakes import ScriptedChatModel

STATE = {"query": "What is the speed of light?", "answer": "299,792,458 m/s", "retries": 0, "documents": []}


def _grade(reply: str, state=STATE):
    llm = ScriptedChatModel(default=reply)
    with patch("backend.ai.nodes.generation.get_llm", return_value=llm):
        return grade_answer(state), llm


def test_disabled_grader_accepts_without_an_llm_call(monkeypatch):
    monkeypatch.setattr(generation.settings, "enable_answer_grader", False)
    result, llm = _grade("no")
    assert result == "useful"
    assert llm.calls == []


@pytest.fixture
def grader_on(monkeypatch):
    monkeypatch.setattr(generation.settings, "enable_answer_grader", True)


def test_retry_limit_accepts_without_an_llm_call(grader_on):
    result, llm = _grade("no", STATE | {"retries": 2})
    assert result == "useful"
    assert llm.calls == []


def test_yes_is_useful(grader_on):
    assert _grade("yes")[0] == "useful"


def test_no_is_not_useful(grader_on):
    assert _grade("no")[0] == "not_useful"
