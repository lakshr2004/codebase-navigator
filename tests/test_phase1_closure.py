import logging
import os
import subprocess
import time

import pytest

from ingestion.scanner import get_repository_files, load_repository
from services import github_loader
from services.github_loader import load_github_repo


def _write(path, content=b"print('ok')\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def test_ignored_only_repository_is_empty(tmp_path):
    _write(tmp_path / ".git" / "config", b"metadata")
    _write(tmp_path / "node_modules" / "package.js")
    _write(tmp_path / "build" / "generated.py")

    assert get_repository_files(str(tmp_path)) == []


def test_empty_and_unsupported_only_repositories_are_safe(tmp_path):
    empty = tmp_path / "empty"
    unsupported = tmp_path / "unsupported"
    empty.mkdir()
    _write(unsupported / "data.csv", b"a,b\n")
    _write(unsupported / "image.bin", b"\x00\x01")

    assert load_repository(str(empty)) == []
    assert load_repository(str(unsupported)) == []


def test_real_permission_fixture_is_used_when_host_enforces_permissions(tmp_path):
    file_path = tmp_path / "restricted.py"
    _write(file_path)
    original_mode = file_path.stat().st_mode
    os.chmod(file_path, 0)
    try:
        try:
            file_path.read_bytes()
        except PermissionError:
            assert get_repository_files(str(tmp_path)) == []
        else:
            pytest.skip("Current host does not enforce chmod permissions for this test user.")
    finally:
        os.chmod(file_path, original_mode)


def test_private_repository_authentication_is_explicitly_unsupported(monkeypatch, tmp_path):
    monkeypatch.setattr(github_loader, "REPOS_DIR", tmp_path)
    monkeypatch.setenv("GITHUB_TOKEN", "secret-token")

    def fail_auth(*args, **kwargs):
        raise subprocess.CalledProcessError(
            128,
            args[0],
            stderr="authentication failed for private repository",
        )

    monkeypatch.setattr(github_loader.subprocess, "run", fail_auth)

    with pytest.raises(ValueError, match="clone failed") as error:
        load_github_repo("https://github.com/private/project")

    assert "secret-token" not in str(error.value)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.performance
def test_scanner_performance_on_deterministic_fixture(tmp_path):
    for index in range(200):
        _write(tmp_path / "src" / f"module_{index:03d}.py")

    started = time.perf_counter()
    files = get_repository_files(str(tmp_path))
    elapsed = time.perf_counter() - started

    assert len(files) == 200
    assert files == sorted(files)
    assert elapsed < 5.0


@pytest.mark.performance
def test_scanner_near_file_count_limit_is_bounded(monkeypatch, tmp_path):
    monkeypatch.setenv("MAX_INDEXED_FILES", "100")
    for index in range(101):
        _write(tmp_path / f"file_{index:03d}.py")

    with pytest.raises(ValueError, match="maximum supported file count"):
        from ingestion.scanner import scan_repository
        scan_repository(str(tmp_path))


def test_skip_reasons_are_not_sensitive(caplog, tmp_path):
    _write(tmp_path / "bad.py", b"\xff\xfe")
    _write(tmp_path / "ignored.csv", b"a,b\n")
    with caplog.at_level(logging.WARNING):
        get_repository_files(str(tmp_path))

    assert "secret-token" not in caplog.text
