import logging
import os
import subprocess

import pytest
from qdrant_client import QdrantClient

from ingestion.scanner import get_repository_files, load_repository, scan_repository
from rag import vector_store
from services import github_loader
from services.github_loader import load_github_repo


def write_file(path, content=b"print('ok')\n"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def create_symlink(path, target, directory=False):
    try:
        os.symlink(target, path, target_is_directory=directory)
    except (OSError, NotImplementedError) as error:
        pytest.skip(f"Symlinks unavailable on this host: {error}")


def test_supported_symlink_policy_skips_internal_external_and_loop_links(tmp_path):
    real_file = tmp_path / "real.py"
    real_dir = tmp_path / "real_dir"
    outside = tmp_path.parent / f"outside-{tmp_path.name}"
    outside.mkdir()
    write_file(real_file)
    write_file(real_dir / "nested.py")
    write_file(outside / "outside.py")

    create_symlink(tmp_path / "internal.py", real_file)
    create_symlink(tmp_path / "linked-dir", real_dir, directory=True)
    create_symlink(tmp_path / "external.py", outside / "outside.py")
    create_symlink(real_dir / "loop", tmp_path, directory=True)

    files = get_repository_files(str(tmp_path))

    assert files == ["real.py", "real_dir/nested.py"]


def test_symlink_escape_is_not_processed_when_supported(tmp_path):
    outside = tmp_path.parent / f"outside-{tmp_path.name}"
    outside.mkdir()
    write_file(outside / "escape.py")
    create_symlink(tmp_path / "escape.py", outside / "escape.py")

    assert get_repository_files(str(tmp_path)) == []


def test_clone_timeout_cleans_temporary_destination(monkeypatch, tmp_path):
    monkeypatch.setattr(github_loader, "REPOS_DIR", tmp_path)

    def timeout(*args, **kwargs):
        destination = args[0][-1]
        os.makedirs(destination, exist_ok=True)
        with open(os.path.join(destination, "partial.txt"), "w", encoding="utf-8") as handle:
            handle.write("partial")
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])

    monkeypatch.setattr(github_loader.subprocess, "run", timeout)

    with pytest.raises(ValueError, match="timed out"):
        load_github_repo("https://github.com/example/project")

    assert list(tmp_path.iterdir()) == []


def test_clone_network_failure_is_actionable_and_secret_safe(monkeypatch, tmp_path):
    monkeypatch.setattr(github_loader, "REPOS_DIR", tmp_path)

    def network_failure(*args, **kwargs):
        raise subprocess.CalledProcessError(
            128,
            args[0],
            stderr="network unavailable token=do-not-leak",
        )

    monkeypatch.setattr(github_loader.subprocess, "run", network_failure)

    with pytest.raises(ValueError, match="clone failed") as error:
        load_github_repo("https://github.com/example/project")

    assert "do-not-leak" not in str(error.value)
    assert "github.com" not in str(error.value)
    assert list(tmp_path.iterdir()) == []


def test_git_missing_is_actionable(monkeypatch, tmp_path):
    monkeypatch.setattr(github_loader, "REPOS_DIR", tmp_path)
    monkeypatch.setattr(
        github_loader.subprocess,
        "run",
        lambda *args, **kwargs: (_ for _ in ()).throw(FileNotFoundError("git")),
    )

    with pytest.raises(ValueError, match="Git executable was not found"):
        load_github_repo("https://github.com/example/project")


def test_private_repository_without_application_auth_is_explicit(monkeypatch, tmp_path):
    monkeypatch.setattr(github_loader, "REPOS_DIR", tmp_path)
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    def auth_failure(*args, **kwargs):
        raise subprocess.CalledProcessError(
            128,
            args[0],
            stderr="authentication required",
        )

    monkeypatch.setattr(github_loader.subprocess, "run", auth_failure)

    with pytest.raises(ValueError, match="clone failed"):
        load_github_repo("https://github.com/private/project")


def test_real_permission_fixture_or_explicit_platform_skip(tmp_path):
    restricted = tmp_path / "restricted.py"
    write_file(restricted)
    original_mode = restricted.stat().st_mode
    os.chmod(restricted, 0)
    try:
        try:
            restricted.read_bytes()
        except PermissionError:
            assert get_repository_files(str(tmp_path)) == []
        else:
            pytest.skip("chmod permissions are not enforced for this test user")
    finally:
        os.chmod(restricted, original_mode)


def test_unreadable_directory_does_not_hide_valid_siblings(tmp_path):
    valid = tmp_path / "valid.py"
    restricted_dir = tmp_path / "restricted"
    write_file(valid)
    write_file(restricted_dir / "hidden.py")
    original_mode = restricted_dir.stat().st_mode
    os.chmod(restricted_dir, 0)
    try:
        try:
            list(restricted_dir.iterdir())
        except PermissionError:
            assert get_repository_files(str(tmp_path)) == ["valid.py"]
        else:
            pytest.skip("directory permissions are not enforced for this test user")
    finally:
        os.chmod(restricted_dir, original_mode)


def test_deleted_file_is_skipped_during_load(monkeypatch, tmp_path):
    target = tmp_path / "deleted.py"
    write_file(target)
    import ingestion.scanner as scanner

    original = scanner.create_document

    def delete_before_read(path, repository_path):
        os.remove(path)
        return original(path, repository_path)

    monkeypatch.setattr(scanner, "create_document", delete_before_read)

    assert load_repository(str(tmp_path)) == []


def test_resource_limits_are_enforced(monkeypatch, tmp_path):
    monkeypatch.setenv("MAX_FILE_SIZE_BYTES", "8")
    monkeypatch.setenv("MAX_INDEXED_FILES", "2")
    monkeypatch.setenv("MAX_DIRECTORY_DEPTH", "1")
    monkeypatch.setenv("MAX_LINE_SIZE_BYTES", "8")
    write_file(tmp_path / "large.py", b"123456789")
    write_file(tmp_path / "deep" / "too_deep.py")
    write_file(tmp_path / "one.py", b"12345678")
    write_file(tmp_path / "two.py", b"12345678")
    write_file(tmp_path / "three.py", b"12345678")

    with pytest.raises(ValueError, match="maximum supported file count"):
        scan_repository(str(tmp_path))

    assert "large.py" not in get_repository_files(str(tmp_path))
    assert "deep/too_deep.py" not in get_repository_files(str(tmp_path))


def test_qdrant_insertion_failure_preserves_existing_collection(monkeypatch):
    class FailingClient:
        def __init__(self):
            self.existing_ids = {"old-id"}
            self.calls = 0

        def collection_exists(self, name):
            return True

        def create_collection(self, **kwargs):
            return None

        def upsert(self, collection_name, points):
            self.calls += 1
            raise RuntimeError("qdrant unavailable")

    client = FailingClient()
    monkeypatch.setattr(vector_store, "get_client", lambda: client)
    monkeypatch.setattr(vector_store, "generate_embedding", lambda text: [0.1, 0.2])

    chunk = [{
        "content": "print('new')",
        "metadata": {
            "filename": "main.py",
            "file_path": "repo/main.py",
            "relative_path": "main.py",
            "language": "python",
            "extension": ".py",
            "chunk_index": 0,
            "start_line": 1,
            "end_line": 1,
        },
    }]

    with pytest.raises(RuntimeError, match="qdrant unavailable"):
        vector_store.insert_chunks(chunk, "repo")

    assert client.existing_ids == {"old-id"}
    assert client.calls == 1


def test_repeated_indexing_uses_stable_ids(monkeypatch):
    class StableClient:
        def collection_exists(self, name):
            return True

        def create_collection(self, **kwargs):
            return None

        def upsert(self, collection_name, points):
            self.ids = [point.id for point in points]

    client = StableClient()
    monkeypatch.setattr(vector_store, "get_client", lambda: client)
    monkeypatch.setattr(vector_store, "generate_embedding", lambda text: [0.1, 0.2])
    chunk = [{
        "content": "print('same')",
        "metadata": {
            "filename": "main.py",
            "file_path": "repo/main.py",
            "relative_path": "main.py",
            "language": "python",
            "extension": ".py",
            "chunk_index": 0,
            "start_line": 1,
            "end_line": 1,
        },
    }]

    vector_store.insert_chunks(chunk, "repo")
    first_ids = list(client.ids)
    vector_store.insert_chunks(chunk, "repo")

    assert client.ids == first_ids


def test_successful_reindex_removes_stale_vectors(monkeypatch):
    class CleanupClient:
        def __init__(self):
            self.deleted = []

        def collection_exists(self, name):
            return True

        def create_collection(self, **kwargs):
            return None

        def upsert(self, collection_name, points):
            self.active_ids = {str(point.id) for point in points}

        def scroll(self, **kwargs):
            class Record:
                def __init__(self, point_id):
                    self.id = point_id

            return [Record("stale-id")], None

        def delete(self, collection_name, points_selector):
            self.deleted.extend(points_selector)

    client = CleanupClient()
    monkeypatch.setattr(vector_store, "get_client", lambda: client)
    monkeypatch.setattr(vector_store, "generate_embedding", lambda text: [0.1, 0.2])

    chunk = [{
        "content": "print('new')",
        "metadata": {
            "filename": "main.py",
            "file_path": "repo/main.py",
            "relative_path": "main.py",
            "language": "python",
            "extension": ".py",
            "chunk_index": 0,
            "start_line": 1,
            "end_line": 1,
        },
    }]

    vector_store.insert_chunks(chunk, "repo")

    assert client.deleted == ["stale-id"]


def test_real_qdrant_reindex_removes_deleted_source_chunk(monkeypatch, tmp_path):
    client = QdrantClient(path=str(tmp_path / "qdrant"))
    monkeypatch.setattr(vector_store, "get_client", lambda: client)
    monkeypatch.setattr(
        vector_store,
        "generate_embedding",
        lambda text: [0.1] * 384,
    )

    def chunk(relative_path, index, content):
        return {
            "content": content,
            "metadata": {
                "filename": relative_path,
                "file_path": str(tmp_path / relative_path),
                "relative_path": relative_path,
                "language": "python",
                "extension": ".py",
                "chunk_index": index,
                "start_line": 1,
                "end_line": 1,
            },
        }

    repository_path = str(tmp_path / "repo")
    first = [
        chunk("old.py", 0, "print('old')"),
        chunk("keep.py", 0, "print('keep')"),
    ]
    second = [chunk("keep.py", 0, "print('keep')")]

    vector_store.insert_chunks(first, repository_path)
    vector_store.insert_chunks(second, repository_path)

    records, _ = client.scroll(
        collection_name=vector_store.get_collection_name(repository_path),
        limit=10,
        with_payload=True,
        with_vectors=False,
    )
    assert len(records) == 1
    assert records[0].payload["metadata"]["relative_path"] == "keep.py"
    client.close()


def test_phase1_logging_does_not_expose_credentials(caplog, tmp_path):
    with caplog.at_level(logging.INFO):
        get_repository_files(str(tmp_path))

    assert "files_discovered=" in caplog.text
    assert "files_indexed=" in caplog.text
    assert "bytes_skipped=" in caplog.text
    assert "GITHUB_TOKEN" not in caplog.text
    assert "secret-token" not in caplog.text
