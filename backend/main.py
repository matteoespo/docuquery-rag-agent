from fastapi import FastAPI
from api.routers import router
from ai.agent import load_agent

app = FastAPI(
    title="DocuQuery RAG Agent",
    description="Local RAG system for technical manuals using Llama3 and Ollama.",
    version="1.0.0"
)

app.include_router(router, prefix="/api", tags=["Agentic RAG"])

@app.get("/health")
async def health_check():
    """Status check for docker"""
    return {"status": "running", "model": "llama3", "db": "chromadb"}

# Load the agent into memory at startup
try:
    print("Loading the agent...")
    app.state.agent = load_agent()
    print("Agent loaded successfully!")
except Exception as e:
    print(f"Error loading the agent: {e}")
    app.state.agent = None
