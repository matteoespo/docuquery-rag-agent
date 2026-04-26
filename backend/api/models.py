# Pydantic schemas (what a QueryRequest or ChatResponse JSON looks like)
from pydantic import BaseModel

class QueryRequest(BaseModel):
    query: str
    chat_history: list[dict] = []  # [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi there!"}]

class ChatResponse(BaseModel):
    question: str
    answer: str