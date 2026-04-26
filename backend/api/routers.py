# Contains endpoints
from typing import List
from fastapi import HTTPException, APIRouter, UploadFile, Request
from .models import QueryRequest
from ai.ingestion import ingest_manual
from ai.state import AgentState

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
    initial_state = AgentState(
        query=query.query,
        documents=[],
        answer="",
        chat_history=query.chat_history
    )
    agent = request.app.state.agent
    if not agent:
        raise HTTPException(status_code=500, detail="Agent not initialized")
    response = agent.invoke(initial_state)
    return {"answer": response["answer"]}