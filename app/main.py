
from pathlib import Path

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
    Return the supported local repositories.
    """

    try:
        return get_supported_repositories()

    except Exception as exc:
        print("Repository listing error:", exc)

        raise HTTPException(
            status_code=500,
            detail="Failed to load repositories",
        )


@app.post(
    "/repositories/load",
    response_model=RepositoryResponse,
)
def load_repository(request: RepositoryRequest):
    """
    Kept for compatibility with the existing API.
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
# SOURCE CODE VIEWER
# ============================================================


@app.get("/repositories/{repository_id}/source")
def get_repository_source(
    repository_id: str,
    file: str,
    start_line: int = 1,
    end_line: int | None = None,
):
    """
    Return a bounded source-code excerpt from a supported repository.

    The requested file must remain inside the selected repository.
    By default, up to 80 lines are returned.
    """

    repository_id = repository_id.strip()

    if not repository_id:
        raise HTTPException(
            status_code=400,
            detail="Repository ID cannot be empty",
        )

    if not file.strip():
        raise HTTPException(
            status_code=400,
            detail="File path cannot be empty",
        )

    if start_line < 1:
        raise HTTPException(
            status_code=400,
            detail="start_line must be at least 1",
        )

    if end_line is not None and end_line < start_line:
        raise HTTPException(
            status_code=400,
            detail="end_line must be greater than or equal to start_line",
        )

    if end_line is not None and end_line - start_line > 500:
        raise HTTPException(
            status_code=400,
            detail="Requested source range is too large",
        )

    try:
        repository_path = get_repository_path(repository_id)

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )

    if not repository_path:
        raise HTTPException(
            status_code=404,
            detail="Repository not found",
        )

    repo_root = Path(repository_path).resolve()
    requested_path = Path(file)

    if requested_path.is_absolute():
        raise HTTPException(
            status_code=400,
            detail="Absolute file paths are not allowed",
        )

    resolved_path = (repo_root / requested_path).resolve()

    # Prevent path traversal, including paths escaping via symlinks.
    try:
        resolved_path.relative_to(repo_root)

    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="File must be inside the selected repository",
        )

    if not resolved_path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Source file not found",
        )

    try:
        lines = resolved_path.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines()

    except OSError as exc:
        print("Source file read error:", exc)

        raise HTTPException(
            status_code=500,
            detail="Could not read source file",
        ) from exc

    if start_line > len(lines):
        raise HTTPException(
            status_code=416,
            detail="start_line exceeds the file length",
        )

    # Return at most 80 lines by default, or the requested range.
    requested_end = (
        end_line
        if end_line is not None
        else start_line + 79
    )

    actual_end = min(requested_end, len(lines))

    return {
        "file": resolved_path.relative_to(repo_root).as_posix(),
        "start_line": start_line,
        "end_line": actual_end,
        "total_lines": len(lines),
        "content": "\n".join(lines[start_line - 1:actual_end]),
    }


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
        result = index_local_repository(repository_id)

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
        print("Repository indexing error:", exc)

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
    """

    query = request.query.strip()

    if not query:
        raise HTTPException(
            status_code=400,
            detail="Query cannot be empty",
        )

    repository_id = request.repository_id.strip()

    if not repository_id:
        raise HTTPException(
            status_code=400,
            detail="Repository ID cannot be empty",
        )

    session_id = request.session_id.strip()

    if not session_id:
        raise HTTPException(
            status_code=400,
            detail="Session ID cannot be empty",
        )

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
        # 1. Resolve repository ID to its local path.
        repository_path = get_repository_path(repository_id)

        if not repository_path:
            raise HTTPException(
                status_code=404,
                detail=f"Repository not found: {repository_id}",
            )

        # 2. Load the existing conversation context.
        conversation_context = build_conversation_context(
            session_id
        )

        # 3. Retrieve relevant code and generate an answer.
        result = answer_query(
            query=query,
            repository_path=repository_path,
            mode=mode,
            conversation_context=conversation_context,
        )

        # 4. Save both messages.
        add_message(
            session_id=session_id,
            role="user",
            content=query,
        )

        add_message(
            session_id=session_id,
            role="assistant",
            content=result["answer"],
        )

        # 5. Return the response.
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
        print("Conversation error:", exc)

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
