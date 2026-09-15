import importlib
import subprocess
import sys
from pathlib import Path

import pytest

from services import github_loader
from services.github_loader import load_github_repo


def test_invalid_repo_url_is_rejected():
    with pytest.raises(ValueError, match="GitHub repository URL"):
        load_github_repo("not-a-github-url")


def test_missing_groq_api_key_is_safe_on_import(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "")

    if "rag.generator" in sys.modules:
        del sys.modules["rag.generator"]

    module = importlib.import_module("rag.generator")

    assert module.GROQ_API_KEY is None
    assert module.client is None
    assert hasattr(module, "generate_answer")


def test_nonexistent_repository_failure_cleans_temporary_clone(monkeypatch, tmp_path):
    monkeypatch.setattr(github_loader, "REPOS_DIR", tmp_path)

    def fail_clone(*args, **kwargs):
        destination = Path(args[0][-1])
        (destination / "partial.txt").write_text("partial", encoding="utf-8")
        raise subprocess.CalledProcessError(
            128,
            args[0],
            stderr="repository not found; token=secret-token",
        )

    monkeypatch.setattr(github_loader.subprocess, "run", fail_clone)

    with pytest.raises(ValueError, match="clone failed") as error:
        load_github_repo("https://github.com/example/missing.git")

    assert "github.com" not in str(error.value)
    assert "secret-token" not in str(error.value)
    assert list(tmp_path.iterdir()) == []


def test_missing_git_is_actionable(monkeypatch, tmp_path):
    monkeypatch.setattr(github_loader, "REPOS_DIR", tmp_path)
    monkeypatch.setattr(
        github_loader.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(FileNotFoundError("git")),
    )

    with pytest.raises(ValueError, match="Git executable was not found"):
        load_github_repo("https://github.com/example/project")

    assert list(tmp_path.iterdir()) == []


def test_clone_timeout_is_actionable_and_cleans_up(monkeypatch, tmp_path):
    monkeypatch.setattr(github_loader, "REPOS_DIR", tmp_path)

    def timeout_clone(*args, **kwargs):
        assert kwargs["timeout"] > 0
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])

    monkeypatch.setattr(github_loader.subprocess, "run", timeout_clone)

    with pytest.raises(ValueError, match="timed out"):
        load_github_repo("https://github.com/example/project")

    assert list(tmp_path.iterdir()) == []


def test_destination_name_is_owner_specific_and_replaced_atomically(monkeypatch, tmp_path):
    monkeypatch.setattr(github_loader, "REPOS_DIR", tmp_path)
    existing = tmp_path / "owner__project"
    existing.mkdir()
    (existing / "old.txt").write_text("old", encoding="utf-8")

    def successful_clone(args, **kwargs):
        destination = Path(args[-1])
        (destination / "new.txt").write_text("new", encoding="utf-8")

    monkeypatch.setattr(github_loader.subprocess, "run", successful_clone)

    result = load_github_repo("https://github.com/owner/project")

    assert result == str(existing)
    assert (existing / "new.txt").read_text(encoding="utf-8") == "new"
    assert not (existing / "old.txt").exists()
    assert len(list(tmp_path.iterdir())) == 1
