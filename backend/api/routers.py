# Contains endpoints
from typing import List, AsyncGenerator
from fastapi import HTTPException, APIRouter, UploadFile, Request
from fastapi.responses import StreamingResponse
from .models import QueryRequest
from ai.ingestion import ingest_manual
from ai.state import AgentState
import json

router = APIRouter()

@router.post("/upload")
async def upload_pdf(files: List[UploadFile]):
    for file in files:
        filename = file.filename
        contents = await file.read()
        with open(f"/app/data/pdfs/{filename}", mode="wb") as f:
            f.write(contents)
    ingest_manual()
    return {"message": f"Successfully uploaded {len(files)} files and ingested into the database.", "doc_count": len(files)}

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

    async for event in agent.astream_events(
        initial_state,
        version="v2",
        config=None
    ):
        event_type = event.get("event")
        tags = event.get("tags", [])
        
        if event_type == "on_chat_model_stream" and "generate_node" in tags:
            chunk = event.get("data", {}).get("chunk")
            if chunk and hasattr(chunk, "content"):
                token = chunk.content
                if token:
                    has_yielded = True
                    yield f"data: {json.dumps({'token': token})}\n\n"
                    
        elif event_type == "on_chain_end" and not has_yielded:
            # Try to capture the final answer from the graph's output if it didn't stream
            output = event.get("data", {}).get("output")
            if isinstance(output, dict) and "answer" in output:
                final_answer = output["answer"]

    # If no tokens were emitted (e.g., out-of-scope query), send the captured answer
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
