import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main import RepositoryInfo, app
from rag.vector_store import get_collection_name
from services.repository_service import get_repository_path, get_supported_repositories


def test_repository_list_exposes_collection_name_and_repository_path() -> None:
    repositories = get_supported_repositories()

    assert repositories

    for repository in repositories:
        assert "id" in repository
        assert "name" in repository
        assert "collection_name" in repository
        assert "repository_path" in repository
        assert "indexed" in repository

        assert Path(repository["repository_path"]).exists()
        assert repository["collection_name"] == get_collection_name(
            repository["repository_path"]
        )

        model = RepositoryInfo(**repository)
        assert model.collection_name == repository["collection_name"]
        assert model.repository_path == repository["repository_path"]


def test_get_repositories_api_returns_repository_path_and_collection_name() -> None:
    with TestClient(app) as client:
        response = client.get("/repositories")

    assert response.status_code == 200
    repositories = response.json()
    assert repositories

    for repository in repositories:
        assert "collection_name" in repository
        assert "repository_path" in repository
        assert repository["collection_name"] == get_collection_name(
            repository["repository_path"]
        )
        assert Path(repository["repository_path"]).exists()


def test_repository_path_is_not_derived_from_collection_name() -> None:
    repository = get_supported_repositories()[0]
    repository_path = repository["repository_path"]
    collection_name = repository["collection_name"]

    assert repository_path
    assert collection_name
    assert repository_path != collection_name
    assert "codebase_chunks_" not in repository_path


def test_resolved_repository_path_matches_supported_repository_directory() -> None:
    repository_path = get_repository_path("monetrik")

    assert str(repository_path).endswith("data/repos/monetrik") or Path("data/repos/monetrik").exists()
    assert Path(repository_path).exists()

    repository = next(
        repo for repo in get_supported_repositories() if repo["id"] == "monetrik"
    )
    assert str(repository_path) == repository["repository_path"]
