# Contains endpoints
from typing import List, AsyncGenerator
from fastapi import HTTPException, APIRouter, UploadFile, Request
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTasks
from .models import QueryRequest
from ai.ingestion import ingest_manual, enrich_with_images, get_ingestion_status
from ai.state import AgentState
import json

router = APIRouter()

@router.post("/upload")
def upload_pdf(files: List[UploadFile], background_tasks: BackgroundTasks):
    for file in files:
        filename = file.filename
        contents = file.file.read()
        with open(f"/app/data/pdfs/{filename}", mode="wb") as f:
            f.write(contents)

    # Phase 1(synchronous): text + tables
    pdf_files = ingest_manual()

    # Phase 2(background): image captioning
    if pdf_files:
        background_tasks.add_task(enrich_with_images, pdf_files)

    return {
        "message": f"Successfully uploaded {len(files)} files. Text and tables ingested. Image captioning running in background.",
        "doc_count": len(files),
    }

@router.get("/ingestion/status")
def ingestion_status() -> dict:
    """Check the progress of background image captioning."""
    return get_ingestion_status()

@router.post("/chat")
async def chat_with_agent(query: QueryRequest, request: Request):
    """Legacy endpoint (non-streaming). Kept for backwards compatibility."""
    initial_state = AgentState(
        query=query.query,
        documents=[],
        answer="",
        chat_history=query.chat_history,
        retries=0
    )
    agent = request.app.state.agent
    if not agent:
        raise HTTPException(status_code=500, detail="Agent not initialized")
    response = await agent.ainvoke(initial_state)
    return {"answer": response["answer"]}

async def generate_tokens(agent, initial_state) -> AsyncGenerator[str, None]:
    """Stream tokens from LangGraph agent using astream_events (v2).
    Filters for 'on_chat_model_stream' events to extract raw text tokens."""
    has_yielded = False
    final_answer = None
    generation_count = 0  # Track how many times the generate node runs

    async for event in agent.astream_events(
        initial_state,
        version="v2",
        config=None
    ):
        event_type = event.get("event")
        tags = event.get("tags", [])
        
        # Detect when the LLM STARTS generating
        if event_type == "on_chat_model_start" and "generate_node" in tags:
            generation_count += 1
            
            # If this is a retry loop (attempt 2+), inject a visual separator into the stream
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

    # If no tokens were streamed (e.g., it hit out_of_scope_node), send the captured answer at the end
    if not has_yielded and final_answer:
        yield f"data: {json.dumps({'token': final_answer})}\n\n"

    yield f"data: {json.dumps({'token': '[stream completed]'})}\n\n"

@router.post("/chat/stream")
async def chat_stream(query: QueryRequest, request: Request):
    """Streaming chat endpoint. Returns Server-Sent Events (SSE) stream of tokens."""
    initial_state = AgentState(
        query=query.query,
        documents=[],
        answer="",
        chat_history=query.chat_history,
        retries=0
    )

    agent = request.app.state.agent
    if not agent:
        raise HTTPException(status_code=500, detail="Agent not initialized")

    return StreamingResponse(
        generate_tokens(agent, initial_state),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
    )
