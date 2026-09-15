import os
import tempfile

import pytest

from core.config import get_runtime_config
from ingestion.scanner import (
    _is_within_repository,
    get_repository_files,
    load_repository,
    normalize_path,
    read_file,
    scan_repository,
)


def _write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(content)


def test_ignored_directories_and_binary_files_are_skipped():
    with tempfile.TemporaryDirectory() as tmpdir:
        os.makedirs(os.path.join(tmpdir, ".git"))
        os.makedirs(os.path.join(tmpdir, "node_modules"))
        os.makedirs(os.path.join(tmpdir, "src"), exist_ok=True)

        _write(os.path.join(tmpdir, ".git", "config"), b"git")
        _write(os.path.join(tmpdir, "node_modules", "pkg.js"), b"console.log('x')")
        _write(os.path.join(tmpdir, "src", "app.py"), b"print('ok')\n")
        _write(os.path.join(tmpdir, "src", "logo.png"), b"\x89PNG\r\n\x1a\n")

        files = get_repository_files(tmpdir)

        assert files == ["src/app.py"]


def test_unsupported_extensions_are_ignored():
    with tempfile.TemporaryDirectory() as tmpdir:
        _write(os.path.join(tmpdir, "notes.md"), b"hello")
        _write(os.path.join(tmpdir, "data.csv"), b"a,b\n")
        _write(os.path.join(tmpdir, "script.py"), b"print('hello')\n")

        files = get_repository_files(tmpdir)

        assert files == ["notes.md", "script.py"]


def test_invalid_utf8_file_is_skipped():
    with tempfile.TemporaryDirectory() as tmpdir:
        _write(os.path.join(tmpdir, "broken.py"), b"\xff\xfe\x00invalid")

        files = get_repository_files(tmpdir)

        assert files == []


def test_invalid_utf8_after_initial_sample_is_skipped():
    with tempfile.TemporaryDirectory() as tmpdir:
        _write(os.path.join(tmpdir, "broken.py"), b"a" * 9000 + b"\xff")

        assert get_repository_files(tmpdir) == []


def test_null_byte_after_initial_sample_is_skipped():
    with tempfile.TemporaryDirectory() as tmpdir:
        _write(os.path.join(tmpdir, "binary.py"), b"a" * 9000 + b"\x00")

        assert get_repository_files(tmpdir) == []


def test_utf8_bom_and_newlines_are_read_correctly():
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, "lines.py")
        _write(file_path, b"\xef\xbb\xbffirst\r\nsecond\n")

        assert read_file(file_path) == "first\nsecond\n"
        assert load_repository(tmpdir)[0]["content"] == "first\nsecond\n"


def test_large_file_is_rejected_by_size_limit():
    config = get_runtime_config()
    max_size = config["max_file_size_bytes"]

    with tempfile.TemporaryDirectory() as tmpdir:
        big_path = os.path.join(tmpdir, "big.py")
        _write(big_path, b"x" * (max_size + 1024))

        files = get_repository_files(tmpdir)

        assert files == []


def test_directory_depth_limit_prunes_deep_directories(monkeypatch):
    monkeypatch.setenv("MAX_DIRECTORY_DEPTH", "2")
    with tempfile.TemporaryDirectory() as tmpdir:
        _write(os.path.join(tmpdir, "root.py"), b"print('root')\n")
        _write(os.path.join(tmpdir, "one", "one.py"), b"print('one')\n")
        _write(os.path.join(tmpdir, "one", "two", "three.py"), b"print('three')\n")

        assert get_repository_files(tmpdir) == ["one/one.py", "root.py"]


def test_long_line_limit_is_enforced(monkeypatch):
    monkeypatch.setenv("MAX_LINE_SIZE_BYTES", "8")
    with tempfile.TemporaryDirectory() as tmpdir:
        _write(os.path.join(tmpdir, "long.py"), b"123456789\n")

        assert get_repository_files(tmpdir) == []


def test_normal_line_under_limit_is_kept(monkeypatch):
    monkeypatch.setenv("MAX_LINE_SIZE_BYTES", "8")
    with tempfile.TemporaryDirectory() as tmpdir:
        _write(os.path.join(tmpdir, "short.py"), b"12345678\n")

        assert get_repository_files(tmpdir) == ["short.py"]


def test_max_file_count_limit_is_enforced(monkeypatch):
    monkeypatch.setenv("MAX_INDEXED_FILES", "2")
    max_files = 2

    with tempfile.TemporaryDirectory() as tmpdir:
        for index in range(max_files + 5):
            _write(os.path.join(tmpdir, f"f{index}.py"), b"print('hi')\n")

        with pytest.raises(ValueError, match="maximum supported file count"):
            scan_repository(tmpdir)


def test_path_traversal_via_symlink_is_blocked():
    with tempfile.TemporaryDirectory() as tmpdir:
        external_root = tempfile.mkdtemp()
        external_path = os.path.join(external_root, "outside.py")
        _write(external_path, b"print('escape')\n")

        repo_dir = os.path.join(tmpdir, "repo")
        os.makedirs(repo_dir)
        link_path = os.path.join(repo_dir, "link.py")

        try:
            os.symlink(external_path, link_path)
        except (OSError, NotImplementedError):
            pytest.skip("Symlinks are unavailable on this platform.")

        files = get_repository_files(repo_dir)

        assert files == []


def _require_symlink(path, target, target_is_directory=False):
    try:
        os.symlink(target, path, target_is_directory=target_is_directory)
    except (OSError, NotImplementedError):
        pytest.skip("Symlinks are unavailable on this platform.")


def test_internal_symlink_is_not_indexed():
    with tempfile.TemporaryDirectory() as tmpdir:
        target = os.path.join(tmpdir, "real.py")
        link = os.path.join(tmpdir, "link.py")
        _write(target, b"print('real')\n")
        _require_symlink(link, target)

        assert get_repository_files(tmpdir) == ["real.py"]


def test_external_symlink_is_not_indexed():
    with tempfile.TemporaryDirectory() as tmpdir, tempfile.TemporaryDirectory() as outside:
        target = os.path.join(outside, "outside.py")
        link = os.path.join(tmpdir, "outside.py")
        _write(target, b"print('outside')\n")
        _require_symlink(link, target)

        assert get_repository_files(tmpdir) == []


def test_symlink_directory_and_loop_do_not_traverse():
    with tempfile.TemporaryDirectory() as tmpdir:
        real_dir = os.path.join(tmpdir, "real")
        os.makedirs(real_dir)
        _write(os.path.join(real_dir, "real.py"), b"print('real')\n")
        _require_symlink(os.path.join(tmpdir, "linked"), real_dir, target_is_directory=True)
        _require_symlink(os.path.join(real_dir, "loop"), tmpdir, target_is_directory=True)

        assert get_repository_files(tmpdir) == ["real/real.py"]


def test_posix_style_relative_path_normalizes_consistently():
    assert normalize_path("src/./nested/../file.py") == normalize_path("src/file.py")


def test_path_containment_rejects_parent_and_cross_drive_paths():
    with tempfile.TemporaryDirectory() as tmpdir:
        assert not _is_within_repository(os.path.join(tmpdir, "..", "outside.py"), tmpdir)
        assert not _is_within_repository("Z:\\outside.py", tmpdir)


def test_nested_repository_metadata_is_not_scanned():
    with tempfile.TemporaryDirectory() as tmpdir:
        _write(os.path.join(tmpdir, "top.py"), b"print('top')\n")
        _write(os.path.join(tmpdir, "nested", ".git", "config"), b"metadata")
        _write(os.path.join(tmpdir, "nested", "nested.py"), b"print('nested')\n")

        assert get_repository_files(tmpdir) == ["nested/nested.py", "top.py"]


def test_deleted_file_during_loading_is_skipped(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = os.path.join(tmpdir, "deleted.py")
        _write(file_path, b"print('deleted')\n")

        original_create = __import__("ingestion.scanner", fromlist=["create_document"]).create_document

        def delete_then_read(path, repository_path):
            os.remove(path)
            return original_create(path, repository_path)

        monkeypatch.setattr("ingestion.scanner.create_document", delete_then_read)
        assert load_repository(tmpdir) == []


def test_unreadable_file_is_skipped(monkeypatch):
    with tempfile.TemporaryDirectory() as tmpdir:
        unreadable = os.path.join(tmpdir, "secret.py")
        _write(unreadable, b"print('secret')\n")

        original_open = open

        def deny_target(path, *args, **kwargs):
            if path == unreadable:
                raise PermissionError("permission denied")
            return original_open(path, *args, **kwargs)

        monkeypatch.setattr("builtins.open", deny_target)
        files = get_repository_files(tmpdir)

        assert files == []


def test_empty_repository_returns_empty_list():
    with tempfile.TemporaryDirectory() as tmpdir:
        assert get_repository_files(tmpdir) == []


def test_repository_with_only_unsupported_files_is_empty():
    with tempfile.TemporaryDirectory() as tmpdir:
        _write(os.path.join(tmpdir, "data.bin"), b"\x00\x01\x02")
        _write(os.path.join(tmpdir, "report.txt"), b"hello")
        assert get_repository_files(tmpdir) == ["report.txt"]


def test_scan_output_is_deterministic():
    with tempfile.TemporaryDirectory() as tmpdir:
        _write(os.path.join(tmpdir, "b.py"), b"print('b')\n")
        _write(os.path.join(tmpdir, "a.py"), b"print('a')\n")
        _write(os.path.join(tmpdir, "nested", "c.py"), b"print('c')\n")

        files = get_repository_files(tmpdir)

        assert files == ["a.py", "b.py", "nested/c.py"]


def test_normalize_paths_are_consistent():
    with tempfile.TemporaryDirectory() as tmpdir:
        nested = os.path.join(tmpdir, "src", "nested")
        os.makedirs(nested)
        file_path = os.path.join(nested, "x.py")
        _write(file_path, b"print('x')\n")

        files = get_repository_files(tmpdir)

        assert files == ["src/nested/x.py"]
        assert "\\" not in files[0]
