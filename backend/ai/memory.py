"""Conversation memory: recent turns as real chat messages.

The model sees prior turns as user/assistant messages (the format it was
trained on) instead of a summary pasted into the system prompt. This also
removes an LLM summarization call per turn and lets Ollama reuse its cache
across a conversation.
"""

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

HISTORY_LIMIT = 6  # most recent messages (3 user/assistant exchanges)


def format_chat_messages(messages: list[dict]) -> str:
    """Format chat messages into a readable plain-text transcript."""
    lines = []
    for message in messages:
        role = str(message.get("role", "unknown")).strip().lower()
        content = str(message.get("content", "")).strip()
        if not content:
            continue
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def history_messages(chat_history: list[dict], limit: int = HISTORY_LIMIT) -> list[BaseMessage]:
    """The most recent user/assistant turns as chat messages (other roles and empty ones dropped)."""
    out: list[BaseMessage] = []
    for message in chat_history:
        content = str(message.get("content", "")).strip()
        role = message.get("role")
        if not content or role not in ("user", "assistant"):
            continue
        out.append(HumanMessage(content) if role == "user" else AIMessage(content))
    return out[-limit:]
