# Pydantic schemas for request and response models in the API.
from pydantic import BaseModel, Field
from typing import Literal

class QueryRequest(BaseModel):
    query: str
    chat_history: list[dict] = []  # [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi there!"}]

class ChatResponse(BaseModel):
    question: str
    answer: str

# route query for guardrail
class RouteRequest(BaseModel):
    """Route a user query to the vectorstore or reject it"""
    datasource: Literal["vector_store", "out_of_scope"] = Field(
        ...,
        description="Route to vectorstore if the query is about technical manuals. Route to out_of_scope if it's general chat, math, or unrelated topics.",
    )
