from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.config import validate_runtime_config

from services.repository_service import (
    get_supported_repositories,
    get_repository_path,
    index_local_repository,
)

from retrieval.search import answer_query

from api.conversation import (
    get_history,
    add_message,
    build_conversation_context,
    clear_history,
)


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="Codebase Navigator AI",
    description="AI-powered codebase understanding and navigation system",
    version="0.1.0",
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)


# ============================================================
# REQUEST / RESPONSE MODELS
# ============================================================


class QueryRequest(BaseModel):
    query: str
    repository_id: str
    session_id: str
    mode: str = "auto"


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
    id: str
    name: str
    collection_name: str
    repository_path: str
    indexed: bool


# ============================================================
# BASIC ROUTES
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
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        )


# ============================================================
# REPOSITORY ROUTES
# ============================================================


@app.get(
    "/repositories",
    response_model=list[RepositoryInfo],
)
def get_repositories():
    """
    Return only the supported local repositories.

    Currently:
        - Monetrik
        - TicketPeChalo.in
    """

    try:
        return get_supported_repositories()

    except Exception as exc:
        print("Repository listing error:", exc)

        raise HTTPException(
            status_code=500,
            detail="Failed to load repositories",
        )


# ------------------------------------------------------------
# Optional GitHub loading route
# ------------------------------------------------------------


@app.post(
    "/repositories/load",
    response_model=RepositoryResponse,
)
def load_repository(request: RepositoryRequest):
    """
    This endpoint is kept for compatibility.

    The current application workflow is focused on the two
    local repositories returned by /repositories.
    """

    repo_url = request.repo_url.strip()

    if not repo_url:
        raise HTTPException(
            status_code=400,
            detail="Repository URL cannot be empty",
        )

    raise HTTPException(
        status_code=400,
        detail=(
            "This version of Codebase Navigator uses the two "
            "configured local repositories. Select a repository "
            "from /repositories instead."
        ),
    )


# ============================================================
# INDEX LOCAL REPOSITORY
# ============================================================


@app.post("/repositories/{repository_id}/index")
def index_repository_route(repository_id: str):
    """
    Index one of the supported local repositories.
    """

    repository_id = repository_id.strip()

    if not repository_id:
        raise HTTPException(
            status_code=400,
            detail="Repository ID cannot be empty",
        )

    try:
        result = index_local_repository(
            repository_id
        )

        return {
            "message": "Repository indexed successfully",
            **result,
        }

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )

    except Exception as exc:
        print(
            "Repository indexing error:",
            exc,
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to index repository",
        )


# ============================================================
# ASK / CONVERSATION
# ============================================================


@app.post(
    "/ask",
    response_model=AskResponse,
)
def ask(request: QueryRequest):
    """
    Ask a question against the selected repository.

    Frontend sends:
        repository_id
        session_id
        mode

    Backend resolves:
        repository_id -> local repository path

    Then retrieval is performed against that repository.
    """

    # --------------------------------------------------------
    # Validate query
    # --------------------------------------------------------

    query = request.query.strip()

    if not query:
        raise HTTPException(
            status_code=400,
            detail="Query cannot be empty",
        )

    # --------------------------------------------------------
    # Validate repository ID
    # --------------------------------------------------------

    repository_id = request.repository_id.strip()

    if not repository_id:
        raise HTTPException(
            status_code=400,
            detail="Repository ID cannot be empty",
        )

    # --------------------------------------------------------
    # Validate session ID
    # --------------------------------------------------------

    session_id = request.session_id.strip()

    if not session_id:
        raise HTTPException(
            status_code=400,
            detail="Session ID cannot be empty",
        )

    # --------------------------------------------------------
    # Validate query mode
    # --------------------------------------------------------

    mode = request.mode.strip().lower()

    if mode not in {"auto", "exact", "semantic"}:
        raise HTTPException(
            status_code=400,
            detail=(
                "Invalid query mode. "
                "Use 'auto', 'exact' or 'semantic'."
            ),
        )

    try:

        # ----------------------------------------------------
        # 1. Resolve repository ID -> local path
        # ----------------------------------------------------

        repository_path = get_repository_path(
            repository_id
        )

        if not repository_path:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Repository not found: "
                    f"{repository_id}"
                ),
            )

        # ----------------------------------------------------
        # 2. Get previous conversation
        # ----------------------------------------------------

        conversation_context = build_conversation_context(
            session_id
        )

        # ----------------------------------------------------
        # 3. Retrieve + generate answer
        # ----------------------------------------------------
        # Keep the current question separate from conversation history.
        # Retrieval should search the repository for the actual question,
        # while the history is available to the retrieval layer only when
        # it is useful for resolving follow-up questions.

        result = answer_query(
            query=query,
            repository_path=repository_path,
            mode=mode,
            conversation_context=conversation_context,
        )

        # ----------------------------------------------------
        # 5. Save user message
        # ----------------------------------------------------

        add_message(
            session_id=session_id,
            role="user",
            content=query,
        )

        # ----------------------------------------------------
        # 6. Save assistant response
        # ----------------------------------------------------

        add_message(
            session_id=session_id,
            role="assistant",
            content=result["answer"],
        )

        # ----------------------------------------------------
        # 7. Return response
        # ----------------------------------------------------

        return {
            "query": query,
            "answer": result["answer"],
            "sources": result["sources"],
        }

    except HTTPException:
        raise

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

    except Exception as exc:
        print(
            "Conversation error:",
            exc,
        )

        raise HTTPException(
            status_code=500,
            detail="Failed to process query",
        )


# ============================================================
# CONVERSATION HISTORY
# ============================================================


@app.get("/conversations/{session_id}")
def get_conversation(session_id: str):

    session_id = session_id.strip()

    if not session_id:
        raise HTTPException(
            status_code=400,
            detail="Session ID cannot be empty",
        )

    return {
        "session_id": session_id,
        "messages": get_history(session_id),
    }


# ============================================================
# CLEAR CONVERSATION
# ============================================================


@app.delete("/conversations/{session_id}")
def delete_conversation(session_id: str):

    session_id = session_id.strip()

    if not session_id:
        raise HTTPException(
            status_code=400,
            detail="Session ID cannot be empty",
        )

    clear_history(session_id)

    return {
        "message": "Conversation history cleared",
        "session_id": session_id,
    }