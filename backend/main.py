"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import router
from ai.agent import load_agent
from core.config import settings
from core.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    logger.info("Loading agent...")
    try:
        app.state.agent = load_agent()
        logger.info("Agent loaded successfully")
    except Exception as e:
        logger.error("Failed to load agent: %s", e)
        app.state.agent = None
    yield


app = FastAPI(
    title="DocuQuery RAG Agent",
    description="Local RAG system for querying technical documentation.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
async def health_check() -> dict:
    """Status check for Docker."""
    return {
        "status": "running",
        "model": settings.llm_model,
        "db": "chromadb",
        "agent_loaded": app.state.agent is not None,
    }
