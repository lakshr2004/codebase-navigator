from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_root_health_and_ready_contract():
    assert client.get("/").status_code == 200
    assert client.get("/health").json()["status"] == "healthy"
    assert client.get("/ready").status_code in {200, 503}


def test_frontend_origin_is_allowed_for_api_requests():
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_repositories_contract():
    with patch("app.main.list_repositories", return_value=[]):
        response = client.get("/repositories")

    assert response.status_code == 200
    assert response.json() == []


def test_repository_load_rejects_empty_input():
    response = client.post("/repositories/load", json={"repo_url": ""})
    assert response.status_code == 400
    assert response.json()["detail"] == "Repository URL cannot be empty"


def test_repository_load_maps_backend_failure():
    with patch("app.main.load_and_index_repository", side_effect=ValueError("clone failed")):
        response = client.post(
            "/repositories/load",
            json={"repo_url": "https://github.com/example/repo"},
        )

    assert response.status_code == 500
    assert response.json()["detail"] == "clone failed"


def test_ask_validation_contract():
    response = client.post("/ask", json={"query": "", "repository_path": "repo", "session_id": "s"})
    assert response.status_code == 400
    assert response.json()["detail"] == "Query cannot be empty"

    response = client.post("/ask", json={"query": "q", "repository_path": "", "session_id": "s"})
    assert response.status_code == 400

    response = client.post("/ask", json={"query": "q", "repository_path": "repo", "session_id": ""})
    assert response.status_code == 400


def test_ask_returns_backend_schema():
    result = {
        "answer": "Found it.",
        "sources": [{
            "file": "src/auth.py",
            "language": "python",
            "start_line": 4,
            "end_line": 8,
            "score": 1.0,
        }],
    }
    with patch("app.main.answer_query", return_value=result):
        response = client.post(
            "/ask",
            json={"query": "Where is loginUser defined?", "repository_path": "repo", "session_id": "s"},
        )

    assert response.status_code == 200
    assert response.json()["answer"] == "Found it."
    assert response.json()["sources"][0]["file"] == "src/auth.py"


def test_ask_backend_failure_is_generic():
    with patch("app.main.answer_query", side_effect=RuntimeError("secret-token")):
        response = client.post(
            "/ask",
            json={"query": "Explain auth", "repository_path": "repo", "session_id": "s"},
        )

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to process query"
    assert "secret-token" not in response.text


def test_conversation_contract():
    assert client.get("/conversations/api-test").status_code == 200
    response = client.delete("/conversations/api-test")
    assert response.status_code == 200
    assert response.json()["session_id"] == "api-test"


def test_missing_required_body_fields_are_validation_errors():
    response = client.post("/ask", json={"query": "hello"})
    assert response.status_code == 422
    assert "detail" in response.json()
