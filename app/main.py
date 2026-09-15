from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from core.config import validate_runtime_config
from services.repository_service import load_and_index_repository
from retrieval.search import answer_query
from rag.vector_store import list_repositories

from api.conversation import (
    get_history,
    add_message,
    build_conversation_context,
    clear_history
)


app = FastAPI(
    title="Codebase Navigator AI",
    description="AI-powered codebase understanding and navigation system",
    version="0.1.0",
)


# ============================================================
# Request / Response Models
# ============================================================

class QueryRequest(BaseModel):
    query: str
    repository_path: str
    session_id: str


class Source(BaseModel):
    file: str
    language: str
    start_line: int | None = None
    end_line: int | None = None
    score: float


class AskResponse(BaseModel):
    query: str
    answer: str
    sources: list[Source]


class RepositoryRequest(BaseModel):
    repo_url: str


class RepositoryResponse(BaseModel):
    message: str
    repository_path: str


class RepositoryInfo(BaseModel):
    name: str
    collection_name: str


# ============================================================
# Basic Routes
# ============================================================

@app.get("/")
def root():
    return {
        "message": "Codebase Navigator AI is running!"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "codebase-navigator",
    }


@app.get("/ready")
def readiness():
    try:
        config = validate_runtime_config()
        return {
            "status": "ready",
            "checks": {
                "app_env": config["app_env"],
                "groq_enabled": config["groq_enabled"],
                "qdrant_enabled": config["qdrant_enabled"],
            },
        }
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


# ============================================================
# Repository Routes
# ============================================================

@app.get(
    "/repositories",
    response_model=list[RepositoryInfo]
)
def get_repositories():

    return list_repositories()


@app.post(
    "/repositories/load",
    response_model=RepositoryResponse
)
def load_repository(request: RepositoryRequest):

    if not request.repo_url.strip():

        raise HTTPException(
            status_code=400,
            detail="Repository URL cannot be empty"
        )

    try:

        repository_path = load_and_index_repository(
            request.repo_url
        )

        return {
            "message": "Repository loaded and indexed successfully",
            "repository_path": repository_path
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# Ask / Conversation Route
# ============================================================

@app.post(
    "/ask",
    response_model=AskResponse
)
def ask(request: QueryRequest):

    # Validate query
    if not request.query.strip():

        raise HTTPException(
            status_code=400,
            detail="Query cannot be empty"
        )

    # Validate repository path
    if not request.repository_path.strip():

        raise HTTPException(
            status_code=400,
            detail="Repository path cannot be empty"
        )

    # Validate session ID
    if not request.session_id.strip():

        raise HTTPException(
            status_code=400,
            detail="Session ID cannot be empty"
        )

    try:

        # ----------------------------------------------------
        # 1. Get previous conversation
        # ----------------------------------------------------

        conversation_context = build_conversation_context(
            request.session_id
        )

        # ----------------------------------------------------
        # 2. Build query with previous context
        # ----------------------------------------------------

        if conversation_context:

            contextual_query = f"""
Previous conversation:

{conversation_context}

Current user question:

{request.query}
"""

        else:

            contextual_query = request.query

        # ----------------------------------------------------
        # 3. Retrieve + generate answer
        # ----------------------------------------------------

        result = answer_query(
            contextual_query,
            request.repository_path
        )

        # ----------------------------------------------------
        # 4. Save user message
        # ----------------------------------------------------

        add_message(
            session_id=request.session_id,
            role="user",
            content=request.query
        )

        # ----------------------------------------------------
        # 5. Save assistant response
        # ----------------------------------------------------

        add_message(
            session_id=request.session_id,
            role="assistant",
            content=result["answer"]
        )

        # ----------------------------------------------------
        # 6. Return response
        # ----------------------------------------------------

        return {
            "query": request.query,
            "answer": result["answer"],
            "sources": result["sources"]
        }

    except ValueError as e:

        raise HTTPException(
            status_code=404,
            detail=str(e)
        )

    except Exception as e:

        print("Conversation error:", e)

        raise HTTPException(
            status_code=500,
            detail="Failed to process query"
        )


# ============================================================
# Conversation History
# ============================================================

@app.get("/conversations/{session_id}")
def get_conversation(session_id: str):

    if not session_id.strip():

        raise HTTPException(
            status_code=400,
            detail="Session ID cannot be empty"
        )

    return {
        "session_id": session_id,
        "messages": get_history(session_id)
    }


# ============================================================
# Clear Conversation
# ============================================================

@app.delete("/conversations/{session_id}")
def delete_conversation(session_id: str):

    if not session_id.strip():

        raise HTTPException(
            status_code=400,
            detail="Session ID cannot be empty"
        )

    clear_history(session_id)

    return {
        "message": "Conversation history cleared",
        "session_id": session_id
    }