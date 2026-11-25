"""API route handlers for upload, chat, and ingestion status."""

import asyncio
import json
import os
from collections.abc import AsyncGenerator
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from langsmith import Client
from starlette.background import BackgroundTasks

from ai.ingestion import (
    delete_document_vectors,
    enrich_with_images,
    get_ingestion_status,
    ingest_manual,
)
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

    # Validate the whole batch before writing anything, so a bad file
    # doesn't leave earlier files on disk without being ingested.
    validated: list[tuple[str, bytes]] = []
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

        # Validate PDF magic bytes (%PDF-)
        if not contents[:5].startswith(b"%PDF-"):
            raise HTTPException(
                status_code=400,
                detail=f"File '{safe_name}' is not a valid PDF (bad magic bytes).",
            )

        validated.append((safe_name, contents))

    saved_paths: list[str] = []
    for safe_name, contents in validated:
        dest = dest_dir / safe_name
        dest.write_bytes(contents)
        saved_paths.append(str(dest))
        logger.info("Saved upload: %s (%d bytes)", safe_name, len(contents))

    # text + tables (only the files in this upload; unchanged files are skipped)
    ingested = await asyncio.to_thread(ingest_manual, saved_paths)

    # image captioning
    if ingested:
        background_tasks.add_task(enrich_with_images, ingested)

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

@router.get("/documents")
def get_documents() -> dict:
    """List all uploaded PDF documents."""
    dest_dir = Path(settings.manual_path)
    if not dest_dir.exists():
        return {"documents": []}
    
    docs = []
    for file_path in dest_dir.glob("*.pdf"):
        # Get file size in MB
        size_mb = file_path.stat().st_size / (1024 * 1024)
        docs.append({
            "filename": file_path.name,
            "size_mb": round(size_mb, 2)
        })
    return {"documents": docs}


@router.delete("/documents/{filename}")
def delete_document(filename: str) -> dict:
    """Delete a PDF document and its associated ChromaDB vectors."""
    if any(c in filename for c in ("/", "\\", "..")):
        raise HTTPException(status_code=400, detail="Invalid filename.")

    file_path = Path(settings.manual_path) / filename
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"Document '{filename}' not found.")

    # Vectors first: if this fails the file stays and the delete can be retried.
    # (Deleting the file first left orphaned vectors nothing would clean up.)
    vectors_deleted = delete_document_vectors(str(file_path))

    file_path.unlink()
    logger.info("Deleted file: %s", file_path)

    return {
        "message": f"Document '{filename}' deleted successfully.",
        "vectors_deleted": vectors_deleted,
    }


@router.get("/documents/{filename}/file")
def get_document_file(filename: str) -> FileResponse:
    """Serve an uploaded PDF inline, so citations can open it (e.g. ``#page=5``)."""
    if any(c in filename for c in ("/", "\\", "..")):
        raise HTTPException(status_code=400, detail="Invalid filename.")
    file_path = Path(settings.manual_path) / filename
    if file_path.suffix.lower() != ".pdf" or not file_path.is_file():
        raise HTTPException(status_code=404, detail=f"Document '{filename}' not found.")
    return FileResponse(file_path, media_type="application/pdf", filename=filename,
                        content_disposition_type="inline")


@router.get("/analytics")
def get_analytics() -> dict:
    """Get analytics data from LangSmith."""
    project_name = os.getenv("LANGSMITH_PROJECT", "default")
    try:
        client = Client()
        runs = list(client.list_runs(
            project_name=project_name,
            is_root=True,  # top-level graph runs (execution_order was removed in langsmith 0.9)
            limit=100
        ))
        
        total_requests = len(runs)
        successes = 0
        latencies = []
        total_tokens = 0
        
        for run in runs:
            if str(run.status).lower() == "success":
                successes += 1
            
            latency = (run.end_time - run.start_time).total_seconds() if run.end_time and run.start_time else 0
            latencies.append(latency)
            
            tokens = (run.prompt_tokens or 0) + (run.completion_tokens or 0)
            total_tokens += tokens
            
        success_rate = (successes / total_requests * 100) if total_requests > 0 else 0
        avg_latency = (sum(latencies) / len(latencies)) if latencies else 0
        
        # Prepare chart data (chronological order)
        latencies.reverse()
        
        return {
            "total_requests": total_requests,
            "success_rate": round(success_rate, 1),
            "avg_latency": round(avg_latency, 2),
            "total_tokens": total_tokens,
            "latencies": latencies,
        }
    except Exception as e:
        logger.error(f"Error fetching analytics: {e}")
        return {
            "total_requests": 0,
            "success_rate": 0,
            "avg_latency": 0,
            "total_tokens": 0,
            "latencies": []
        }


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


# Shown to the user while a node runs, until the answer starts streaming.
NODE_STATUS = {
    "contextualize": "Understanding your follow-up question...",
    "retrieve": "Searching your documents...",
    "websearch": "Searching the web...",
    "generate": "Writing the answer...",
}


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def _sources(documents) -> list[dict]:
    """Retrieved chunks as {source, page, url}, de-duplicated, in retrieval order."""
    seen, out = set(), []
    for doc in documents:
        source = str(doc.metadata.get("source", ""))
        is_web = source.startswith(("http://", "https://"))
        name = source if is_web else os.path.basename(source)
        page = None if is_web else doc.metadata.get("page")
        if not name or (name, page) in seen:
            continue
        seen.add((name, page))
        out.append({"source": name, "page": page, "url": source if is_web else None})
    return out


async def generate_tokens(agent, initial_state: AgentState) -> AsyncGenerator[str, None]:
    """Server-sent events for one answer. Each event is ``{"type": ...}``:

    - ``status``: what the agent is doing (until the answer starts)
    - ``sources``: the chunks the answer is generated from (sent before its tokens)
    - ``token``: a piece of the answer
    - ``reset``: the answer so far was rejected and is being regenerated
    - ``error``: the agent failed (instead of ``done``)
    - ``done``: the answer is complete
    """
    try:
        async for event in _answer_events(agent, initial_state):
            yield event
    except Exception:
        logger.exception("Agent failed while answering")
        message = "Something went wrong while generating the answer. Check that Ollama is running and try again."
        yield _sse({"type": "error", "message": message})


async def _answer_events(agent, initial_state: AgentState) -> AsyncGenerator[str, None]:
    has_yielded = False
    final_answer = None
    generation_count = 0
    documents = []
    has_history = bool(initial_state.get("chat_history"))

    async for event in agent.astream_events(initial_state, version="v2", config=None):
        event_type = event.get("event")
        tags = event.get("tags", [])
        name = event.get("name")
        # A node's own run (not one of the runnables inside it).
        is_node = name in NODE_STATUS and event.get("metadata", {}).get("langgraph_node") == name

        if event_type == "on_chain_start" and is_node and not has_yielded:
            if name != "contextualize" or has_history:  # no rewrite happens without history
                yield _sse({"type": "status", "text": NODE_STATUS[name]})

        elif event_type == "on_chain_end" and is_node and name in ("retrieve", "websearch"):
            output = event.get("data", {}).get("output") or {}
            documents = output.get("documents", documents)

        elif event_type == "on_chat_model_start" and "generate_node" in tags:
            generation_count += 1
            if generation_count > 1:
                # The previous answer was rejected by the grader: the client
                # discards what it has shown before the new answer streams in.
                has_yielded = False
                yield _sse({"type": "reset", "status": NODE_STATUS["websearch"]})
            yield _sse({"type": "sources", "sources": _sources(documents)})

        elif event_type == "on_chat_model_stream" and "generate_node" in tags:
            chunk = event.get("data", {}).get("chunk")
            token = getattr(chunk, "content", None)
            if token:
                has_yielded = True
                yield _sse({"type": "token", "text": token})

        # Non-streamed answers (the out-of-scope reply)
        elif event_type == "on_chain_end" and not has_yielded:
            output = event.get("data", {}).get("output")
            if isinstance(output, dict) and output.get("answer"):
                final_answer = output["answer"]

    if not has_yielded and final_answer:
        yield _sse({"type": "token", "text": final_answer})
    yield _sse({"type": "done"})


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
