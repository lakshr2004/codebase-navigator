import importlib

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_and_readiness_endpoints():
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "healthy"

    ready = client.get("/ready")
    assert ready.status_code == 200
    payload = ready.json()
    assert payload["status"] == "ready"
    assert "checks" in payload


def test_missing_required_config_is_explicit():
    module = importlib.import_module("core.config")
    assert hasattr(module, "get_runtime_config")

    cfg = module.get_runtime_config()
    assert "app_env" in cfg
    assert "groq_enabled" in cfg
    assert "qdrant_enabled" in cfg
