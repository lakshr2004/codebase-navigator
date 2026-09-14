from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


# ============================================================
# Test 1: Root endpoint
# ============================================================

def test_root():

    response = client.get("/")

    assert response.status_code == 200

    data = response.json()

    assert data["message"] == (
        "Codebase Navigator AI is running!"
    )


# ============================================================
# Test 2: Health endpoint
# ============================================================

def test_health():

    response = client.get("/health")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "healthy"


# ============================================================
# Test 3: Empty query validation
# ============================================================

def test_empty_query():

    response = client.post(
        "/ask",
        json={
            "query": "",
            "repository_path": "data/test",
            "session_id": "test-session"
        }
    )

    assert response.status_code == 400

    assert response.json()["detail"] == (
        "Query cannot be empty"
    )


# ============================================================
# Test 4: Empty repository path validation
# ============================================================

def test_empty_repository_path():

    response = client.post(
        "/ask",
        json={
            "query": "What is this project?",
            "repository_path": "",
            "session_id": "test-session"
        }
    )

    assert response.status_code == 400

    assert response.json()["detail"] == (
        "Repository path cannot be empty"
    )


# ============================================================
# Test 5: Empty session ID validation
# ============================================================

def test_empty_session_id():

    response = client.post(
        "/ask",
        json={
            "query": "What is this project?",
            "repository_path": "data/test",
            "session_id": ""
        }
    )

    assert response.status_code == 400

    assert response.json()["detail"] == (
        "Session ID cannot be empty"
    )


# ============================================================
# Test 6: Empty repository URL validation
# ============================================================

def test_empty_repository_url():

    response = client.post(
        "/repositories/load",
        json={
            "repo_url": ""
        }
    )

    assert response.status_code == 400

    assert response.json()["detail"] == (
        "Repository URL cannot be empty"
    )


# ============================================================
# Test 7: Conversation history
# ============================================================

def test_get_conversation():

    response = client.get(
        "/conversations/test-session"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["session_id"] == "test-session"

    assert "messages" in data


# ============================================================
# Test 8: Clear conversation
# ============================================================

def test_delete_conversation():

    response = client.delete(
        "/conversations/test-session"
    )

    assert response.status_code == 200

    data = response.json()

    assert data["session_id"] == "test-session"

    assert data["message"] == (
        "Conversation history cleared"
    )