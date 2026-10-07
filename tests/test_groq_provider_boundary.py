import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rag import generator


def make_source(**kwargs):
    source = {
        "evidence_id": 1,
        "file": "auth.py",
        "start_line": 1,
        "end_line": 2,
    }
    source.update(kwargs)
    return source


def make_response_payload(answer: str, evidence_ids: list[int]):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=json.dumps({
                        "answer": answer,
                        "evidence_ids": evidence_ids,
                    })
                )
            )
        ]
    )


def test_test_mode_is_deterministic_and_never_instantiates_real_groq(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr(generator, "client", None)

    called = {"count": 0}

    class FakeGroq:
        def __init__(self, *args, **kwargs):
            called["count"] += 1
            raise AssertionError("real Groq client should not be instantiated in test mode")

    monkeypatch.setattr(generator, "Groq", FakeGroq)

    result = generator.generate_grounded_answer(
        "How does authentication work?",
        "def loginUser(username, password):\n    return verify_credentials(username, password)",
        [make_source()],
    )

    assert result == {"answer": generator.FALLBACK_RESPONSE, "evidence_ids": []}
    assert called["count"] == 0


def test_missing_groq_api_key_raises_explicit_config_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setattr(generator, "client", None)

    result = generator.generate_grounded_answer(
        "How does authentication work?",
        "def loginUser():\n    return True",
        [make_source()],
    )

    assert "GROQ_API_KEY" in result["answer"]
    assert "I couldn't find enough information in the codebase." not in result["answer"]
    assert result["evidence_ids"] == []


def test_invalid_groq_credentials_raise_explicit_auth_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("GROQ_API_KEY", "bad-key")
    monkeypatch.setattr(generator, "client", None)

    class FakeGroq:
        def __init__(self, api_key=None):
            raise RuntimeError("401 unauthorized")

    monkeypatch.setattr(generator, "Groq", FakeGroq)

    result = generator.generate_grounded_answer(
        "How does authentication work?",
        "def loginUser():\n    return True",
        [make_source()],
    )

    assert "authentication failed" in result["answer"].lower()
    assert "401" in result["answer"]
    assert result["evidence_ids"] == []


def test_groq_api_failure_is_explicit_not_refusal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("GROQ_API_KEY", "live-key")
    monkeypatch.setattr(generator, "client", None)

    class FakeGroq:
        def __init__(self, api_key=None):
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("simulated Groq outage"))
                )
            )

    monkeypatch.setattr(generator, "Groq", FakeGroq)

    result = generator.generate_grounded_answer(
        "How does authentication work?",
        "def loginUser():\n    return True",
        [make_source()],
    )

    assert result["answer"].startswith("LLM provider request failed")
    assert result["evidence_ids"] == []
    assert result["answer"] != generator.FALLBACK_RESPONSE


def test_empty_groq_response_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("GROQ_API_KEY", "live-key")
    monkeypatch.setattr(generator, "client", None)

    class FakeGroq:
        def __init__(self, api_key=None):
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **kwargs: SimpleNamespace(
                        choices=[SimpleNamespace(message=SimpleNamespace(content="   "))]
                    )
                )
            )

    monkeypatch.setattr(generator, "Groq", FakeGroq)

    result = generator.generate_grounded_answer(
        "How does authentication work?",
        "def loginUser():\n    return True",
        [make_source()],
    )

    assert "empty response" in result["answer"].lower()
    assert result["evidence_ids"] == []


def test_malformed_groq_response_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("GROQ_API_KEY", "live-key")
    monkeypatch.setattr(generator, "client", None)

    class FakeGroq:
        def __init__(self, api_key=None):
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **kwargs: SimpleNamespace(
                        choices=[SimpleNamespace(message=SimpleNamespace(content="{not-json"))]
                    )
                )
            )

    monkeypatch.setattr(generator, "Groq", FakeGroq)

    result = generator.generate_grounded_answer(
        "How does authentication work?",
        "def loginUser():\n    return True",
        [make_source()],
    )

    assert "malformed json" in result["answer"].lower()
    assert result["evidence_ids"] == []


def test_successful_mocked_groq_response_is_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("GROQ_API_KEY", "live-key")
    monkeypatch.setattr(generator, "client", None)

    class FakeGroq:
        def __init__(self, api_key=None):
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **kwargs: make_response_payload(
                        "loginUser verifies credentials.",
                        [1],
                    )
                )
            )

    monkeypatch.setattr(generator, "Groq", FakeGroq)

    result = generator.generate_grounded_answer(
        "How does authentication work?",
        "def loginUser(username, password):\n    return verify_credentials(username, password)",
        [make_source()],
    )

    assert result == {"answer": "loginUser verifies credentials.", "evidence_ids": [1]}


def test_invalid_source_metadata_is_rejected_before_llm_call(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("GROQ_API_KEY", "live-key")
    monkeypatch.setattr(generator, "client", None)

    bad_sources = [{"evidence_id": 1, "file": "auth.py", "start_line": 5, "end_line": 2}]
    result = generator.generate_grounded_answer(
        "How does authentication work?",
        "def loginUser():\n    return True",
        bad_sources,
    )

    assert result == {"answer": generator.FALLBACK_RESPONSE, "evidence_ids": []}


def test_cross_repository_source_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("GROQ_API_KEY", "live-key")
    monkeypatch.setattr(generator, "client", None)

    bad_sources = [{"evidence_id": 1, "file": "../outside.py", "start_line": 1, "end_line": 2}]
    result = generator.generate_grounded_answer(
        "How does authentication work?",
        "def loginUser():\n    return True",
        bad_sources,
    )

    assert result == {"answer": generator.FALLBACK_RESPONSE, "evidence_ids": []}


def test_production_mode_does_not_fall_back_to_deterministic_output(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("GROQ_API_KEY", "live-key")
    monkeypatch.setattr(generator, "client", None)

    class FakeGroq:
        def __init__(self, api_key=None):
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **kwargs: make_response_payload(
                        "loginUser verifies credentials.",
                        [1],
                    )
                )
            )

    monkeypatch.setattr(generator, "Groq", FakeGroq)

    result = generator.generate_grounded_answer(
        "How does authentication work?",
        "def loginUser(username, password):\n    return verify_credentials(username, password)",
        [make_source()],
    )

    assert result["answer"] != generator.FALLBACK_RESPONSE
    assert result["answer"] == "loginUser verifies credentials."


def test_honest_rag_refusal_is_distinct_from_llm_operational_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("GROQ_API_KEY", "live-key")
    monkeypatch.setattr(generator, "client", None)

    class FakeGroq:
        def __init__(self, api_key=None):
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **kwargs: make_response_payload(
                        generator.FALLBACK_RESPONSE,
                        [],
                    )
                )
            )

    monkeypatch.setattr(generator, "Groq", FakeGroq)

    refusal = generator.generate_grounded_answer(
        "How does authentication work?",
        "One unrelated file",
        [make_source()],
    )
    assert refusal == {"answer": generator.FALLBACK_RESPONSE, "evidence_ids": []}

    class FailGroq:
        def __init__(self, api_key=None):
            self.chat = SimpleNamespace(
                completions=SimpleNamespace(
                    create=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("simulated Groq outage"))
                )
            )

    monkeypatch.setattr(generator, "Groq", FailGroq)
    operational = generator.generate_grounded_answer(
        "How does authentication work?",
        "def loginUser():\n    return True",
        [make_source()],
    )

    assert operational["answer"] != generator.FALLBACK_RESPONSE
    assert "LLM provider request failed" in operational["answer"]
    assert operational["evidence_ids"] == []
