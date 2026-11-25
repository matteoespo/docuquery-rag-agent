"""Pydantic schemas for API request/response models and LLM structured output."""

from typing import Literal

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """A single chat message."""
    role: Literal["user", "assistant", "system"]
    content: str


class QueryRequest(BaseModel):
    """Incoming chat query with optional conversation history."""
    query: str = Field(
        min_length=1,
        max_length=5000,
        description="The user's question (1-5000 characters).",
    )
    chat_history: list[ChatMessage] = Field(
        default_factory=list,
        max_length=50,
        description="Previous conversation messages (max 50).",
    )
