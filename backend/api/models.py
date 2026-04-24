# Pydantic schemas (what a QueryRequest or ChatResponse JSON looks like)
from pydantic import BaseModel

class QueryRequest(BaseModel):
    query: str

class ChatResponse(BaseModel):
    respose: str