# Contains endpoints

from fastapi import HTTPException, APIRouter, UploadFile
from .models import QueryRequest
from ai.rag_engine import get_rag_chain
from ai.ingestion import ingest_manual

router = APIRouter()

@router.post("/upload")
async def upload_pdf(file: UploadFile):
    filename = file.filename
    contents = await file.read()
    with open("/app/data/pdfs/manual.pdf", mode="wb") as f:
        f.write(contents)
    
    ingest_manual()
    return {"message": "PDF received and sent to chunking"}

@router.post("/chat")
async def chat_with_agent(query: QueryRequest):
    chain = get_rag_chain()
    response = chain.invoke({"input": query})
    return {"answer": response["answer"]}