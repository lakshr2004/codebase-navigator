import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rag import generator
from retrieval import search


REFUSAL = "I couldn't find enough information in the codebase."


@pytest.fixture
def repository(tmp_path: Path) -> Path:
    files = {
        "auth.py": (
            "def loginUser(username, password):\n"
            "    return verify_credentials(username, password)\n"
        ),
        "transactions.py": (
            "def save_transaction(transaction, database):\n"
            "    database.insert(transaction)\n"
        ),
        "seats.py": (
            "def lock_seat(seat_id, expires_at):\n"
            "    seat_locks[seat_id] = expires_at\n"
        ),
        "frontend/api.js": (
            "export async function loadProfile() {\n"
            "  return fetch('/api/profile');\n"
            "}\n"
        ),
        "unrelated.py": (
            "def format_date(value):\n"
            "    return value.isoformat()\n"
        ),
        "package-lock.json": (
            '{\"name\":\"fixture\",\"dependencies\":{\"redis\":\"1.0.0\"}}\n'
        ),
    }
    for relative_path, content in files.items():
        target = tmp_path / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return tmp_path


def _result(
    repository: Path,
    relative_path: str,
    start_line: int,
    end_line: int,
    score: float = 0.9,
) -> SimpleNamespace:
    return SimpleNamespace(
        score=score,
        payload={
            "content": "Indexed chunk content is not trusted as source text.",
            "metadata": {
                "relative_path": relative_path,
                "language": "python",
                "start_line": start_line,
                "end_line": end_line,
            },
        },
    )


def _grounded_answer(answer: str, evidence_ids: list[int]):
    def generate(*, query, context, sources):
        assert "[Evidence ID:" in context
        return {"answer": answer, "evidence_ids": evidence_ids}

    return generate


@pytest.mark.parametrize(
    ("query", "supporting_file", "start_line", "end_line", "answer"),
    [
        (
            "How does authentication work?",
            "auth.py",
            1,
            2,
            "loginUser verifies the supplied username and password.",
        ),
        (
            "How are transactions stored?",
            "transactions.py",
            1,
            2,
            "save_transaction inserts the transaction into the supplied database.",
        ),
        (
            "How does seat locking work?",
            "seats.py",
            1,
            2,
            "lock_seat stores an expiry value for the seat ID in seat_locks.",
        ),
        (
            "How does the frontend communicate with the backend?",
            "frontend/api.js",
            1,
            3,
            "loadProfile requests /api/profile with fetch.",
        ),
    ],
)
def test_semantic_answers_return_only_cited_current_source_lines(
    monkeypatch: pytest.MonkeyPatch,
    repository: Path,
    query: str,
    supporting_file: str,
    start_line: int,
    end_line: int,
    answer: str,
) -> None:
    # The decoy comes first so its evidence ID differs from the supporting source.
    monkeypatch.setattr(
        search,
        "search_code",
        lambda **kwargs: [
            _result(repository, "unrelated.py", 1, 2),
            _result(repository, supporting_file, start_line, end_line),
        ],
    )
    monkeypatch.setattr(
        search,
        "is_identifier_query",
        lambda query: False,
    )
    monkeypatch.setattr(
        generator,
        "generate_grounded_answer",
        _grounded_answer(answer, [2]),
    )

    result = search.answer_query(query, str(repository), mode="semantic")

    assert result["answer"] == answer
    assert len(result["sources"]) == 1
    source = result["sources"][0]
    assert source["file"] == supporting_file
    assert (source["start_line"], source["end_line"]) == (start_line, end_line)
    assert "content" not in source
    assert "evidence_id" not in source
    assert "unrelated.py" not in {item["file"] for item in result["sources"]}
    assert "package-lock.json" not in {item["file"] for item in result["sources"]}


def test_definition_query_returns_exact_definition_lines(repository: Path) -> None:
    result = search.answer_query("Where is loginUser defined?", str(repository))

    assert result["answer"].startswith("Found definition(s) for `loginUser`")
    assert len(result["sources"]) == 1
    assert result["sources"][0]["file"] == "auth.py"
    assert (result["sources"][0]["start_line"], result["sources"][0]["end_line"]) == (1, 1)


@pytest.mark.parametrize(
    "query",
    [
        "Where is startGame defined?",
        "Where is xyzDefinitelyDoesNotExist defined?",
        "Where is SomeCompletelyNonexistentService implemented?",
    ],
)
def test_missing_identifiers_refuse_without_sources(query: str, repository: Path) -> None:
    result = search.answer_query(query, str(repository))

    assert result == {"answer": REFUSAL, "sources": []}


@pytest.mark.parametrize(
    ("query", "irrelevant_file"),
    [
        ("How is Redis configured?", "auth.py"),
        ("How is the PostgreSQL connection created?", "transactions.py"),
    ],
)
def test_unsupported_infrastructure_claims_refuse_without_irrelevant_sources(
    monkeypatch: pytest.MonkeyPatch,
    repository: Path,
    query: str,
    irrelevant_file: str,
) -> None:
    monkeypatch.setattr(
        search,
        "search_code",
        lambda **kwargs: [_result(repository, irrelevant_file, 1, 2)],
    )
    monkeypatch.setattr(search, "is_identifier_query", lambda query: False)
    monkeypatch.setattr(
        generator,
        "generate_grounded_answer",
        _grounded_answer(REFUSAL, []),
    )

    result = search.answer_query(query, str(repository), mode="semantic")

    assert result == {"answer": REFUSAL, "sources": []}
    assert "Redis" not in result["answer"]
    assert "PostgreSQL" not in result["answer"]


def test_invalid_or_stale_retrieved_source_is_not_evidence(
    monkeypatch: pytest.MonkeyPatch,
    repository: Path,
) -> None:
    monkeypatch.setattr(
        search,
        "search_code",
        lambda **kwargs: [
            _result(repository, "../outside.py", 1, 1),
            _result(repository, "unrelated.py", 1, 3),
        ],
    )
    monkeypatch.setattr(search, "is_identifier_query", lambda query: False)

    result = search.answer_query(
        "How does authentication work?",
        str(repository),
        mode="semantic",
    )

    assert result == {"answer": REFUSAL, "sources": []}


def test_lockfiles_are_never_returned_as_semantic_evidence(
    monkeypatch: pytest.MonkeyPatch,
    repository: Path,
) -> None:
    monkeypatch.setattr(
        search,
        "search_code",
        lambda **kwargs: [
            _result(repository, "package-lock.json", 1, 1),
            _result(repository, "auth.py", 1, 2),
        ],
    )
    monkeypatch.setattr(search, "is_identifier_query", lambda query: False)
    monkeypatch.setattr(
        generator,
        "generate_grounded_answer",
        _grounded_answer("loginUser verifies credentials.", [1]),
    )

    result = search.answer_query(
        "How does authentication work?",
        str(repository),
        mode="semantic",
    )

    assert len(result["sources"]) == 1
    assert result["sources"][0]["file"] == "auth.py"
    assert (result["sources"][0]["start_line"], result["sources"][0]["end_line"]) == (1, 2)


@pytest.mark.parametrize(
    "content",
    [
        "not json",
        json.dumps({"answer": "Unsupported assertion", "evidence_ids": []}),
        json.dumps({"answer": "Unsupported assertion", "evidence_ids": [999]}),
        json.dumps({"answer": "Unsupported assertion", "evidence_ids": "1"}),
        json.dumps({"answer": "", "evidence_ids": [1]}),
    ],
)
def test_generator_rejects_invalid_or_uncited_llm_output(
    monkeypatch: pytest.MonkeyPatch,
    content: str,
) -> None:
    message = SimpleNamespace(content=content)
    response = SimpleNamespace(choices=[SimpleNamespace(message=message)])
    fake_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=lambda **kwargs: response)
        )
    )
    monkeypatch.setattr(generator, "client", fake_client)
    sources = [{"evidence_id": 1, "file": "auth.py", "start_line": 1, "end_line": 1}]

    result = generator.generate_grounded_answer(
        "How does authentication work?",
        "[Evidence ID: 1]\nCode: def loginUser(): pass",
        sources,
    )

    assert result == {"answer": REFUSAL, "evidence_ids": []}


def test_generator_api_failure_returns_explicit_llm_error(monkeypatch, caplog) -> None:
    def raise_api_error(**kwargs):
        raise RuntimeError("simulated Groq outage")

    fake_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=raise_api_error)
        )
    )
    monkeypatch.setattr(generator, "client", fake_client)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    sources = [{"evidence_id": 1, "file": "auth.py", "start_line": 1, "end_line": 1}]

    result = generator.generate_grounded_answer(
        "How does authentication work?",
        "[Evidence ID: 1]\nCode: def loginUser(): pass",
        sources,
    )

    assert result["answer"].startswith("LLM provider request failed")
    assert result["evidence_ids"] == []
    assert "LLM provider request failed" in caplog.text or "LLM provider request failed" in result["answer"]


def test_generator_keeps_only_known_evidence_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    content = json.dumps({
        "answer": "loginUser verifies the provided credentials.",
        "evidence_ids": [2, 999, 2],
    })
    message = SimpleNamespace(content=content)
    response = SimpleNamespace(choices=[SimpleNamespace(message=message)])
    fake_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=lambda **kwargs: response)
        )
    )
    monkeypatch.setattr(generator, "client", fake_client)
    sources = [
        {"evidence_id": 1, "file": "unrelated.py", "start_line": 1, "end_line": 1},
        {"evidence_id": 2, "file": "auth.py", "start_line": 1, "end_line": 2},
    ]

    result = generator.generate_grounded_answer(
        "How does authentication work?",
        "[Evidence ID: 1]\nCode: def unrelated(): pass\n"
        "[Evidence ID: 2]\nCode: def loginUser(): pass",
        sources,
    )

    assert result == {
        "answer": "loginUser verifies the provided credentials.",
        "evidence_ids": [2],
    }


def test_generator_does_not_truncate_context_away_from_its_source_catalog(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_call(**kwargs):
        raise AssertionError("oversized context must not be sent to Groq")

    fake_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=unexpected_call)
        )
    )
    monkeypatch.setattr(generator, "client", fake_client)

    result = generator.generate_grounded_answer(
        "Explain this code",
        "x" * (generator.MAX_CONTEXT_CHARS + 1),
        [{"evidence_id": 1, "file": "auth.py", "start_line": 1, "end_line": 1}],
    )

    assert result == {"answer": REFUSAL, "evidence_ids": []}
