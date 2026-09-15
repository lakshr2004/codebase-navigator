import os
from typing import Any


_DEFAULT_ENV = "development"

_DEFAULT_MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024
_DEFAULT_MAX_INDEXED_FILES = 25000
_DEFAULT_MAX_DIRECTORY_DEPTH = 50
_DEFAULT_MAX_LINE_SIZE_BYTES = 1024 * 1024
_DEFAULT_GITHUB_CLONE_TIMEOUT_SECONDS = 300


def _read_positive_int(name: str, default: int) -> int:
    raw_value = os.getenv(name, str(default)).strip()
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value <= 0:
        raise ValueError(f"{name} must be greater than 0")
    return value


def get_runtime_config() -> dict[str, Any]:
    """Return runtime configuration for the current environment.

    This is intentionally defensive: the app should not crash during import if
    development/test credentials are absent, but production mode should fail with
    explicit validation errors when required settings are missing.
    """
    app_env = (os.getenv("APP_ENV") or _DEFAULT_ENV).strip().lower() or _DEFAULT_ENV
    groq_api_key = (os.getenv("GROQ_API_KEY") or "").strip()
    qdrant_url = (os.getenv("QDRANT_URL") or "").strip()
    qdrant_path = (os.getenv("QDRANT_PATH") or "data/qdrant").strip() or "data/qdrant"
    hf_token = (os.getenv("HF_TOKEN") or "").strip()

    max_file_size_bytes = _read_positive_int(
        "MAX_FILE_SIZE_BYTES", _DEFAULT_MAX_FILE_SIZE_BYTES
    )
    max_indexed_files = _read_positive_int(
        "MAX_INDEXED_FILES", _DEFAULT_MAX_INDEXED_FILES
    )
    max_directory_depth = _read_positive_int(
        "MAX_DIRECTORY_DEPTH", _DEFAULT_MAX_DIRECTORY_DEPTH
    )
    max_line_size_bytes = _read_positive_int(
        "MAX_LINE_SIZE_BYTES", _DEFAULT_MAX_LINE_SIZE_BYTES
    )
    github_clone_timeout_seconds = _read_positive_int(
        "GITHUB_CLONE_TIMEOUT_SECONDS", _DEFAULT_GITHUB_CLONE_TIMEOUT_SECONDS
    )

    return {
        "app_env": app_env,
        "debug": app_env != "production",
        "groq_enabled": bool(groq_api_key),
        "qdrant_enabled": bool(qdrant_url) or os.path.isdir(qdrant_path),
        "qdrant_url": qdrant_url,
        "qdrant_path": qdrant_path,
        "hf_token_configured": bool(hf_token),
        "requires_api_credentials": app_env == "production",
        "max_file_size_bytes": max_file_size_bytes,
        "max_indexed_files": max_indexed_files,
        "max_directory_depth": max_directory_depth,
        "max_line_size_bytes": max_line_size_bytes,
        "github_clone_timeout_seconds": github_clone_timeout_seconds,
    }


def validate_runtime_config() -> dict[str, Any]:
    """Raise a descriptive error if required production configuration is missing."""
    try:
        config = get_runtime_config()
    except ValueError as exc:
        raise RuntimeError(f"Invalid runtime configuration: {exc}") from exc
    missing: list[str] = []

    if config["app_env"] == "production":
        if not config["groq_enabled"]:
            missing.append("GROQ_API_KEY")
        if not config["qdrant_enabled"]:
            missing.append("QDRANT_URL or QDRANT_PATH")

    if missing:
        raise RuntimeError(
            "Missing required production configuration: " + ", ".join(missing)
        )

    return config
