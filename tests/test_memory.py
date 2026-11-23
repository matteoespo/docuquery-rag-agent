"""Conversation memory: summarization must not block the event loop."""

import asyncio
import time
from unittest.mock import patch

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from backend.ai.memory import build_memory_context

SLOW = 0.3


class SlowChatModel(BaseChatModel):
    """Takes SLOW seconds to answer: blocking in sync, awaiting in async."""

    @property
    def _llm_type(self) -> str:
        return "slow-fake"

    def _result(self) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=" - summary "))])

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        time.sleep(SLOW)
        return self._result()

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs):
        await asyncio.sleep(SLOW)
        return self._result()


HISTORY = [
    {"role": "user" if i % 2 == 0 else "assistant", "content": f"message {i}"}
    for i in range(6)
]


def test_empty_history_returns_empty_string():
    assert asyncio.run(build_memory_context([])) == ""


@patch("backend.ai.memory.get_llm", return_value=SlowChatModel())
def test_summarization_does_not_block_event_loop(_):
    async def scenario():
        ticks = 0
        done = asyncio.Event()

        async def ticker():
            nonlocal ticks
            while not done.is_set():
                ticks += 1
                await asyncio.sleep(0.01)

        task = asyncio.create_task(ticker())
        result = await build_memory_context(HISTORY)
        done.set()
        await task
        return result, ticks

    result, ticks = asyncio.run(scenario())

    # A blocking call would freeze the ticker for the whole SLOW window.
    assert ticks >= 10
    assert "Older conversation summary:\n- summary" in result
    assert "assistant: message 5" in result
    assert "message 0" not in result.split("Most recent")[1]
