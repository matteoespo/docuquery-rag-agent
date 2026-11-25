"""Conversation memory: recent turns become real chat messages (no summarization LLM call)."""

from langchain_core.messages import AIMessage, HumanMessage

from backend.ai.memory import format_chat_messages, history_messages


def test_history_becomes_user_and_assistant_messages():
    history = [
        {"role": "user", "content": "What is the KX-200?"},
        {"role": "assistant", "content": "A conveyor controller."},
    ]
    assert history_messages(history) == [
        HumanMessage("What is the KX-200?"),
        AIMessage("A conveyor controller."),
    ]


def test_history_keeps_only_the_most_recent_messages():
    history = [{"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}"} for i in range(10)]
    assert [m.content for m in history_messages(history, limit=4)] == ["m6", "m7", "m8", "m9"]


def test_history_drops_empty_and_non_chat_roles():
    history = [
        {"role": "system", "content": "ignore me"},
        {"role": "user", "content": "   "},
        {"role": "user", "content": "real question"},
    ]
    assert history_messages(history) == [HumanMessage("real question")]


def test_format_chat_messages_transcript():
    history = [{"role": "user", "content": " hi "}, {"role": "assistant", "content": ""}]
    assert format_chat_messages(history) == "user: hi"
