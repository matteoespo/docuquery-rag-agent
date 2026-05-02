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

class RetrievalEvalRequest(BaseModel):
    """Assess if the retrieved documents contain enough information to answer the query"""
    datasource: Literal["vector_store", "more_info_needed"] = Field(
        ...,
        description="Route to vector_store if the documents contain the answer. Route to more_info_needed if they do not.",
    )

class GradeAnswerResponse(BaseModel):
    """Assess whether the generated answer is useful and resolves the user's query"""
    is_useful: Literal["yes", "no"] = Field(
        ...,
        description="Type 'yes' if the answer directly addresses the user's question and is informative. Type 'no' if it does not.",
    )

