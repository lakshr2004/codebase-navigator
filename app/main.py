from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from services.repository_service import load_and_index_repository
from retrieval.search import answer_query
from rag.vector_store import list_repositories


app = FastAPI(
    title="Codebase Navigator AI",
    description="AI-powered codebase understanding and navigation system",
    version="0.1.0",
)


class QueryRequest(BaseModel):
    query: str
    repository_path: str


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


@app.get("/")
def root():
    return {
        "message": "Codebase Navigator AI is running!"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }

class RepositoryInfo(BaseModel):
    name: str
    collection_name: str


@app.get("/repositories", response_model=list[RepositoryInfo])
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


@app.post("/ask", response_model=AskResponse)
def ask(request: QueryRequest):

    if not request.query.strip():
        raise HTTPException(
            status_code=400,
            detail="Query cannot be empty"
        )

    if not request.repository_path.strip():
        raise HTTPException(
            status_code=400,
            detail="Repository path cannot be empty"
        )

    try:
        result = answer_query(
            request.query,
            request.repository_path
        )

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
        raise HTTPException(
            status_code=500,
            detail="Failed to process query"
        )