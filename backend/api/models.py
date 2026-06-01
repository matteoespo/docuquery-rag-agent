"""Pydantic schemas for API request/response models and LLM structured output."""

from pydantic import BaseModel, Field
from typing import Literal


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


class ChatResponse(BaseModel):
    """Chat endpoint response."""
    question: str
    answer: str


# LLM structured output schemas

class RouteDecision(BaseModel):
    """Route a user query to the vectorstore or reject it."""
    datasource: Literal["vector_store", "out_of_scope"] = Field(
        description="Route to vectorstore if the query is about technical manuals. "
                    "Route to out_of_scope if it's general chat, math, or unrelated topics.",
    )


class RetrievalEvaluation(BaseModel):
    """Assess if retrieved documents contain enough information to answer the query."""
    datasource: Literal["vector_store", "more_info_needed"] = Field(
        description="Route to vector_store if the documents contain the answer. "
                    "Route to more_info_needed if they do not.",
    )
