# Contains endpoints
from typing import List
from fastapi import HTTPException, APIRouter, UploadFile, Request
from .models import QueryRequest
from ai.ingestion import ingest_manual
from ai.state import AgentState

#authentication imports
from core.db import get_db
from core.auth import authenticate_user, create_user, create_access_token
from sqlalchemy.orm import Session

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
        chat_history=query.chat_history,
        retries=0
    )
    agent = request.app.state.agent
    if not agent:
        raise HTTPException(status_code=500, detail="Agent not initialized")
    response = await agent.ainvoke(initial_state)
    return {"answer": response["answer"]}


@router.post("/login")
def login(request: Request, username: str, password: str, db: Session = next(get_db())):
    user = authenticate_user(db, username, password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")

    access_token = create_access_token(data={"sub": user.username})
    return {"message": "Login successful", "access_token": access_token}

@router.post("/register")
def register(request: Request, username: str, password: str, db: Session = next(get_db())):
    try:
        user = create_user(db, username, password)
        if not user:
            raise HTTPException(status_code=400, detail="User registration failed")
        login(request, username, password, db)  # Automatically log in the user after registration
        return {"message": "User created successfully"}
    except HTTPException as e:
        raise e
    except Exception:
        raise HTTPException(status_code=500, detail="An error occurred while creating the user")
    

@router.post("/logout")
def logout(request: Request, token: str):
    # In a real application, you would implement token blacklisting here
    return {"message": "Logout successful"}