"""Conversation memory utilities for the agent.

Provides helpers to format and compress chat history into
a context block that fits within the LLM's token budget.
"""

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from ai.llm import get_llm
from core.logger import get_logger

logger = get_logger(__name__)


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


async def build_memory_context(chat_history: list[dict]) -> str:
    """Keep recent messages verbatim and summarize older conversation.

    Async so the summarization LLM call doesn't block the event loop when
    called from the async ``generate`` node.
    """
    if not chat_history:
        return ""

    recent_messages = chat_history[-3:]
    older_messages = chat_history[:-3]

    recent_block = format_chat_messages(recent_messages)
    older_summary = ""

    if older_messages:
        summarize_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    "Summarize the prior conversation for assistant memory. "
                    "Capture user goals, constraints, preferences, and unresolved topics in 4 concise bullet points max.",
                ),
                ("human", "Conversation:\n{conversation}"),
            ]
        )
        summarize_chain = summarize_prompt | get_llm() | StrOutputParser()
        try:
            older_summary = (await summarize_chain.ainvoke(
                {"conversation": format_chat_messages(older_messages)}
            )).strip()
        except Exception as e:
            logger.warning("Memory summarization failed: %s", e)
            older_summary = format_chat_messages(older_messages[-2:])

    memory_sections = []
    if older_summary:
        memory_sections.append(f"Older conversation summary:\n{older_summary}")
    if recent_block:
        memory_sections.append(f"Most recent 3 messages:\n{recent_block}")

    return "\n\n".join(memory_sections)
