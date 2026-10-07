from pathlib import Path

from services.indexer import index_repository
from rag.vector_store import collection_exists, get_collection_name


# ============================================================
# LOCAL REPOSITORIES
# ============================================================

REPOS_DIR = Path("data/repos")


SUPPORTED_REPOSITORIES = {
    "monetrik": REPOS_DIR / "monetrik",
    "ticketpechalo": REPOS_DIR / "TicketPeChalo.in",
}


# ============================================================
# GET SUPPORTED REPOSITORIES
# ============================================================

def get_supported_repositories():
    """
    Return only the repositories currently supported
    by Codebase Navigator.
    """

    repositories = []

    for repository_id, repository_path in SUPPORTED_REPOSITORIES.items():

        # Repository must exist
        if not repository_path.exists():
            continue

        # Repository must be a directory
        if not repository_path.is_dir():
            continue

        repository_path_string = str(
            repository_path
        )
        collection_name = get_collection_name(
            repository_path_string
        )

        repositories.append(
            {
                "id": repository_id,
                "name": repository_path.name,
                "collection_name": collection_name,
                "repository_path": repository_path_string,
                "indexed": collection_exists(
                    repository_path_string
                ),
            }
        )

    return repositories


# ============================================================
# RESOLVE REPOSITORY ID
# ============================================================

def get_repository_path(repository_id: str) -> Path:
    """
    Resolve a supported repository ID to its local path.

    Supported IDs:

        monetrik
        ticketpechalo
    """

    if not repository_id:
        raise ValueError(
            "Repository ID is required"
        )

    repository_id = repository_id.strip().lower()

    if repository_id not in SUPPORTED_REPOSITORIES:
        raise ValueError(
            f"Unsupported repository: {repository_id}"
        )

    repository_path = SUPPORTED_REPOSITORIES[
        repository_id
    ]

    # Repository must exist
    if not repository_path.exists():
        raise FileNotFoundError(
            f"Repository does not exist: {repository_path}"
        )

    # Repository must be a directory
    if not repository_path.is_dir():
        raise ValueError(
            f"Repository path is not a directory: {repository_path}"
        )

    return repository_path


# ============================================================
# INDEX LOCAL REPOSITORY
# ============================================================

def index_local_repository(repository_id: str):
    """
    Re-index one of the supported local repositories.

    Flow:

        repository_id
              ↓
        resolve local path
              ↓
        index_repository()
              ↓
        Qdrant collection
    """

    if not repository_id:
        raise ValueError(
            "Repository ID is required"
        )

    normalized_repository_id = (
        repository_id.strip().lower()
    )

    repository_path = get_repository_path(
        normalized_repository_id
    )

    # Run complete indexing pipeline
    collection_name = index_repository(
        str(repository_path)
    )

    return {
        "id": normalized_repository_id,
        "name": repository_path.name,
        "repository_path": str(repository_path),
        "collection_name": collection_name,
        "indexed": True,
    }