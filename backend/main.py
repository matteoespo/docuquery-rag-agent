from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from ai.rag_engine import get_rag_chain

app = FastAPI(
    title="DocuQuery RAG Agent",
    description="Local RAG system for technical manuals using Llama3 and Ollama.",
    version="1.0.0"
)

# Load the RAG chain into memory at startup
try:
    print("Loading AI Model and Vector DB...")
    rag_chain = get_rag_chain()
    print("AI Engine ready.")
except Exception as e:
    print(f"Error loading RAG Engine: {e}")
    rag_chain = None

# API Data Models
class QuestionRequest(BaseModel):
    question: str

class AnswerResponse(BaseModel):
    question: str
    answer: str

# Endpoints
@app.get("/health")
async def health_check():
    """Status check for Docker/Kubernetes orchestration."""
    return {"status": "running", "model": "llama3", "db": "chromadb"}

@app.post("/api/v1/ask", response_model=AnswerResponse)
async def ask_question(request: QuestionRequest):
    """
    Endpoint to ask questions about the industrial manual.
    The agent will retrieve context and generate a local response.
    """
    if not rag_chain:
        raise HTTPException(status_code=500, detail="AI Engine not initialized.")

    try:
        result = rag_chain.invoke({"input": request.question})
        return AnswerResponse(
            question=request.question,
            answer=result["answer"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))