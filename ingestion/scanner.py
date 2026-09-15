import os
import stat
import codecs
import logging

from core.config import get_runtime_config


logger = logging.getLogger(__name__)


# ============================================================
# Supported File Types
# ============================================================

SUPPORTED_EXTENSIONS = {
    # Python
    ".py",

    # JavaScript / TypeScript
    ".js",
    ".jsx",
    ".ts",
    ".tsx",

    # Java / C-family
    ".java",
    ".cpp",
    ".c",
    ".h",
    ".hpp",

    # Other programming languages
    ".go",
    ".rs",

    # Web
    ".html",
    ".htm",
    ".css",
    ".scss",
    ".sass",
    ".less",
    ".svg",

    # Data / Configuration
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".xml",
    ".env.example",

    # Documentation
    ".md",
    ".mdx",
    ".txt",

    # Shell
    ".sh",

    # Database
    ".sql",
}

SUPPORTED_FILENAMES = {
    "dockerfile",
    "makefile",
    "requirements.txt",
    "package.json",
    ".gitignore",
    ".dockerignore",
    "license",
    "gemfile",
    "rakefile",
    "cmakelists.txt",
}

BINARY_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp",
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    ".zip", ".tar", ".gz", ".7z", ".rar",
    ".pdf", ".exe", ".dll", ".so", ".dylib", ".class", ".pyc", ".o", ".obj",
    ".db", ".sqlite", ".sqlite3", ".bin", ".dat",
    ".mp3", ".mp4", ".wav", ".avi", ".mov",
}


# ============================================================
# Ignored Directories
# ============================================================

IGNORED_DIRECTORIES = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".idea",
    ".vscode",
    "dist",
    "build",
    "coverage",
    ".next",
    ".nuxt",
    "target",
    ".cache",
    "bin",
    "obj",
    ".tox",
    ".hypothesis",
    ".ruff_cache",
}


# ============================================================
# Language Mapping
# ============================================================

LANGUAGE_MAP = {
    # Python
    ".py": "python",

    # JavaScript / TypeScript
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",

    # Java / C-family
    ".java": "java",
    ".cpp": "cpp",
    ".c": "c",
    ".h": "c",
    ".hpp": "cpp",

    # Other programming languages
    ".go": "go",
    ".rs": "rust",

    # Web
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "scss",
    ".sass": "sass",
    ".less": "less",
    ".svg": "svg",

    # Data / Configuration
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".xml": "xml",

    # Documentation
    ".md": "markdown",
    ".mdx": "markdown",
    ".txt": "text",

    # Shell
    ".sh": "shell",

    # Database
    ".sql": "sql",
}

LANGUAGE_EXTENSION_MAP = {
    "python": {".py"},
    "javascript": {".js", ".jsx"},
    "typescript": {".ts", ".tsx"},
    "java": {".java"},
    "cpp": {".cpp", ".hpp"},
    "c": {".c", ".h"},
    "go": {".go"},
    "rust": {".rs"},
    "html": {".html", ".htm"},
    "css": {".css", ".scss", ".sass", ".less"},
    "scss": {".scss"},
    "sass": {".sass"},
    "less": {".less"},
    "json": {".json"},
    "markdown": {".md", ".mdx"},
    "yaml": {".yaml", ".yml"},
    "shell": {".sh"},
    "sql": {".sql"},
    "toml": {".toml"},
    "xml": {".xml"},
    "svg": {".svg"},
}


# ============================================================
# Path Helpers
# ============================================================

def normalize_path(file_path: str) -> str:
    """Normalize a filesystem path, handling Windows and POSIX separators."""
    if not file_path:
        return ""
    return os.path.normpath(os.path.abspath(file_path))


def get_relative_path(file_path: str, repository_path: str) -> str:
    """Return a repository-relative path with forward slashes '/'."""
    absolute_file = normalize_path(file_path)
    absolute_repository = normalize_path(repository_path)

    relative_path = os.path.relpath(absolute_file, absolute_repository)
    return relative_path.replace("\\", "/")


def _is_within_repository(file_path: str, repository_path: str) -> bool:
    """Return True when the input path stays inside the repository root."""
    try:
        common = os.path.commonpath([
            os.path.normcase(os.path.realpath(file_path)),
            os.path.normcase(os.path.realpath(repository_path)),
        ])
    except ValueError:
        return False
    return os.path.normcase(os.path.realpath(repository_path)) == common


def _relative_depth(file_path: str, repository_path: str) -> int:
    relative_path = os.path.relpath(file_path, repository_path)
    if relative_path in {".", ""}:
        return 0
    return len(relative_path.split(os.sep))


def _should_ignore_directory(directory_name: str) -> bool:
    normalized = directory_name.lower()
    if normalized in IGNORED_DIRECTORIES:
        return True
    if normalized.startswith(".") and normalized not in {".env.example"}:
        return True
    return False


def _is_text_file_safe(file_path: str) -> bool:
    """Skip unreadable, binary, invalid UTF-8, or pathological source files."""
    try:
        if os.path.islink(file_path):
            return False
        if not os.path.isfile(file_path):
            return False
        mode = os.stat(file_path).st_mode
        if not mode & (stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH):
            return False
        config = get_runtime_config()
        if os.path.getsize(file_path) > config["max_file_size_bytes"]:
            return False
        decoder = codecs.getincrementaldecoder("utf-8")()
        line_size = 0
        with open(file_path, "rb") as handle:
            while True:
                chunk = handle.read(64 * 1024)
                if not chunk:
                    break
                if b"\x00" in chunk:
                    return False
                decoded = decoder.decode(chunk)
                for character in decoded:
                    if character == "\n":
                        line_size = 0
                    else:
                        line_size += len(character.encode("utf-8"))
                        if line_size > config["max_line_size_bytes"]:
                            return False
            decoder.decode(b"", final=True)
    except (OSError, UnicodeDecodeError, ValueError):
        return False
    return True


def is_binary_file(file_path: str) -> bool:
    """Check if a file is a binary file based on extension or quick chunk inspection."""
    extension = os.path.splitext(file_path)[1].lower()
    if extension in BINARY_EXTENSIONS:
        return True

    if os.path.isfile(file_path):
        try:
            with open(file_path, "rb") as f:
                chunk = f.read(1024)
                if b"\x00" in chunk:
                    return True
        except OSError:
            pass

    return False


def is_supported_file(file_path: str) -> bool:
    """Check if a file should be scanned and indexed."""
    filename = os.path.basename(file_path).lower()
    if filename in SUPPORTED_FILENAMES:
        return True

    extension = os.path.splitext(filename)[1].lower()
    if extension in BINARY_EXTENSIONS:
        return False

    return extension in SUPPORTED_EXTENSIONS


def get_file_language(file_path: str) -> str:
    """Determine the programming or markup language of a file."""
    filename = os.path.basename(file_path).lower()
    if filename == "dockerfile":
        return "dockerfile"
    if filename == "makefile":
        return "makefile"

    extension = os.path.splitext(filename)[1].lower()
    return LANGUAGE_MAP.get(extension, "unknown")


# ============================================================
# Repository Scanner (Canonical Functions)
# ============================================================

def get_repository_files(repository_path: str) -> list[str]:
    """Scan a repository and return a deterministic list of safe relative paths."""
    repository_path = normalize_path(repository_path)
    if not os.path.isdir(repository_path):
        return []

    config = get_runtime_config()
    max_file_size = max(int(config.get("max_file_size_bytes", 10 * 1024 * 1024)), 1)
    files: list[str] = []
    seen_real_paths: set[str] = set()

    max_directory_depth = int(config.get("max_directory_depth", 50))

    for root, directories, filenames in os.walk(repository_path, topdown=True, followlinks=False):
        root_depth = _relative_depth(root, repository_path)
        directories[:] = [
            directory
            for directory in directories
            if not os.path.islink(os.path.join(root, directory))
            and not _should_ignore_directory(directory)
            and _is_within_repository(os.path.join(root, directory), repository_path)
        ]
        if root_depth >= max_directory_depth:
            directories[:] = []

        for filename in sorted(filenames):
            absolute_path = normalize_path(os.path.join(root, filename))

            if _relative_depth(absolute_path, repository_path) > max_directory_depth:
                continue
            if os.path.islink(absolute_path):
                continue
            if not _is_within_repository(absolute_path, repository_path):
                continue
            if not is_supported_file(filename):
                continue
            if is_binary_file(absolute_path):
                continue
            try:
                if os.path.getsize(absolute_path) > max_file_size:
                    continue
            except OSError:
                continue
            if not _is_text_file_safe(absolute_path):
                continue

            relative_path = get_relative_path(absolute_path, repository_path)
            if relative_path in {".", ".."} or relative_path.startswith("../"):
                continue

            real_path = os.path.normcase(os.path.realpath(absolute_path))
            if real_path in seen_real_paths:
                continue

            seen_real_paths.add(real_path)
            files.append(relative_path.replace("\\", "/"))

    return sorted(files)


def get_repository_folders(repository_path: str) -> list[str]:
    """Return directory-relative folder paths, excluding ignored and unsafe ones."""
    repository_path = normalize_path(repository_path)
    if not os.path.isdir(repository_path):
        return []

    folders = set()
    max_directory_depth = int(get_runtime_config().get("max_directory_depth", 50))
    for root, directories, _ in os.walk(repository_path, topdown=True, followlinks=False):
        root_depth = _relative_depth(root, repository_path)
        directories[:] = [
            directory
            for directory in directories
            if not os.path.islink(os.path.join(root, directory))
            and not _should_ignore_directory(directory)
            and _is_within_repository(os.path.join(root, directory), repository_path)
        ]
        if root_depth >= max_directory_depth:
            directories[:] = []

        for directory in directories:
            absolute_path = normalize_path(os.path.join(root, directory))
            if not _is_within_repository(absolute_path, repository_path):
                continue
            relative_path = get_relative_path(absolute_path, repository_path)
            if relative_path and relative_path not in {".", ".."}:
                folders.add(relative_path.replace("\\", "/"))

    return sorted(folders)


def scan_repository(repository_path: str) -> list[str]:
    """Scan a repository and return absolute paths of all supported source files."""
    repository_path = normalize_path(repository_path)

    if not os.path.exists(repository_path):
        raise ValueError(f"Repository does not exist: {repository_path}")
    if not os.path.isdir(repository_path):
        raise ValueError(f"Repository path is not a directory: {repository_path}")

    rel_files = get_repository_files(repository_path)
    config = get_runtime_config()
    max_indexed_files = int(config.get("max_indexed_files", 25000))
    if len(rel_files) > max_indexed_files:
        raise ValueError(
            f"Repository exceeds the maximum supported file count ({max_indexed_files})."
        )

    files = [
        normalize_path(os.path.join(repository_path, f.replace("/", os.sep)))
        for f in rel_files
    ]
    return sorted(files)


# ============================================================
# File Reader
# ============================================================

def read_file(file_path: str) -> str:
    """Read a source file using UTF-8, removing an optional BOM."""
    try:
        with open(file_path, "r", encoding="utf-8-sig", errors="replace") as file:
            return file.read()
    except OSError as e:
        raise ValueError(f"Failed to read file {file_path}: {e}")


# ============================================================
# File Metadata
# ============================================================

def get_file_metadata(file_path: str, repository_path: str | None = None) -> dict:
    """Generate standardized metadata for a repository file."""
    file_path = normalize_path(file_path)
    filename = os.path.basename(file_path)
    extension = os.path.splitext(filename)[1].lower()
    language = get_file_language(filename)

    metadata = {
        "file_path": file_path,
        "filename": filename,
        "relative_path": "",
        "language": language,
        "extension": extension,
        "repository_path": ""
    }

    if repository_path:
        repository_path = normalize_path(repository_path)
        metadata["repository_path"] = repository_path
        metadata["relative_path"] = get_relative_path(file_path, repository_path)

    return metadata


# ============================================================
# Document Creation & Loading
# ============================================================

def create_document(file_path: str, repository_path: str | None = None) -> dict:
    """Create a document containing file content and standardized metadata."""
    metadata = get_file_metadata(file_path, repository_path)
    content = read_file(file_path)
    return {"content": content, "metadata": metadata}


def load_repository(repository_path: str) -> list[dict]:
    """Scan and load all supported repository files."""
    repository_path = normalize_path(repository_path)
    files = scan_repository(repository_path)
    documents = []

    for file_path in files:
        try:
            document = create_document(file_path, repository_path)
            documents.append(document)
        except ValueError as e:
            logger.warning("Skipping file %s: %s", file_path, e)

    return documents