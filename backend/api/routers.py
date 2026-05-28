"""API route handlers for upload, chat, and ingestion status."""

import asyncio
import json
from collections.abc import AsyncGenerator
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTasks

from ai.ingestion import enrich_with_images, get_ingestion_status, ingest_manual
from ai.state import AgentState
from api.models import QueryRequest
from core.config import settings
from core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["Agentic RAG"])


@router.post("/upload")
async def upload_pdf(
    files: list[UploadFile],
    background_tasks: BackgroundTasks,
) -> dict:
    """Upload PDFs, ingest text/tables (sync), and caption images (background)."""
    if len(files) > settings.max_upload_files:
        raise HTTPException(
            status_code=400,
            detail=f"Too many files. Maximum {settings.max_upload_files} allowed.",
        )

    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    dest_dir = Path(settings.manual_path)
    dest_dir.mkdir(parents=True, exist_ok=True)

    for file in files:
        # Sanitise filename
        safe_name = Path(file.filename or "upload.bin").name
        if not safe_name.lower().endswith(".pdf"):
            raise HTTPException(
                status_code=400,
                detail=f"Only PDF files are accepted. Got: {safe_name}",
            )

        contents = await file.read()
        if len(contents) > max_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"File '{safe_name}' exceeds the {settings.max_upload_size_mb} MB limit.",
            )

        (dest_dir / safe_name).write_bytes(contents)
        logger.info("Saved upload: %s (%d bytes)", safe_name, len(contents))

    # text + tables
    pdf_files = await asyncio.to_thread(ingest_manual)

    # image captioning
    if pdf_files:
        background_tasks.add_task(enrich_with_images, pdf_files)

    return {
        "message": (
            f"Successfully uploaded {len(files)} file(s). "
            "Text and tables ingested. Image captioning running in background."
        ),
        "doc_count": len(files),
    }


@router.get("/ingestion/status")
def ingestion_status() -> dict:
    """Check the progress of background image captioning."""
    return get_ingestion_status()


@router.post("/chat")
async def chat_with_agent(query: QueryRequest, request: Request) -> dict:
    """Legacy endpoint (non-streaming). Kept for backwards compatibility."""
    agent = request.app.state.agent
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized. Try again later.")

    initial_state = AgentState(
        query=query.query,
        documents=[],
        answer="",
        chat_history=[msg.model_dump() for msg in query.chat_history],
        retries=0,
    )
    response = await agent.ainvoke(initial_state)
    return {"answer": response["answer"]}


async def generate_tokens(agent, initial_state: AgentState) -> AsyncGenerator[str, None]:
    """Stream tokens from LangGraph agent using astream_events (v2).

    Filters for 'on_chat_model_stream' events to extract raw text tokens.
    """
    has_yielded = False
    final_answer = None
    generation_count = 0

    async for event in agent.astream_events(
        initial_state,
        version="v2",
        config=None,
    ):
        event_type = event.get("event")
        tags = event.get("tags", [])

        # Detect when the LLM STARTS generating
        if event_type == "on_chat_model_start" and "generate_node" in tags:
            generation_count += 1
            if generation_count > 1:
                separator = "\n\n> **Searching the web for more information...**\n\n"
                yield f"data: {json.dumps({'token': separator})}\n\n"

        # Stream the raw text tokens
        elif event_type == "on_chat_model_stream" and "generate_node" in tags:
            chunk = event.get("data", {}).get("chunk")
            if chunk and hasattr(chunk, "content"):
                token = chunk.content
                if token:
                    has_yielded = True
                    yield f"data: {json.dumps({'token': token})}\n\n"

        # Catch non-streaming responses (like the out-of-scope block node)
        elif event_type == "on_chain_end" and not has_yielded:
            output = event.get("data", {}).get("output")
            if isinstance(output, dict) and "answer" in output:
                final_answer = output["answer"]

    if not has_yielded and final_answer:
        yield f"data: {json.dumps({'token': final_answer})}\n\n"

    yield f"data: {json.dumps({'token': '[stream completed]'})}\n\n"


@router.post("/chat/stream")
async def chat_stream(query: QueryRequest, request: Request):
    """Streaming chat endpoint. Returns Server-Sent Events (SSE) stream of tokens."""
    agent = request.app.state.agent
    if not agent:
        raise HTTPException(status_code=503, detail="Agent not initialized. Try again later.")

    initial_state = AgentState(
        query=query.query,
        documents=[],
        answer="",
        chat_history=[msg.model_dump() for msg in query.chat_history],
        retries=0,
    )

    return StreamingResponse(
        generate_tokens(agent, initial_state),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
