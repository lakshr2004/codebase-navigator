import os


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

    # Data / Configuration
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".xml",

    # Documentation
    ".md",
    ".mdx",

    # Shell
    ".sh",

    # Database
    ".sql",
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

    # Data / Configuration
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".toml": "toml",
    ".xml": "xml",

    # Documentation
    ".md": "markdown",
    ".mdx": "markdown",

    # Shell
    ".sh": "shell",

    # Database
    ".sql": "sql",
}


# ============================================================
# Path Helpers
# ============================================================

def normalize_path(file_path: str) -> str:
    """
    Normalize a filesystem path.

    This keeps path handling consistent across
    Windows and other operating systems.
    """
    return os.path.normpath(
        os.path.abspath(file_path)
    )


def get_relative_path(
    file_path: str,
    repository_path: str
) -> str:
    """
    Return a repository-relative path.

    Example:

        repository:
            data/repos/Bubble-Game

        file:
            data/repos/Bubble-Game/script.js

        result:
            script.js
    """

    absolute_file = normalize_path(file_path)
    absolute_repository = normalize_path(repository_path)

    relative_path = os.path.relpath(
        absolute_file,
        absolute_repository
    )

    return relative_path.replace("\\", "/")


# ============================================================
# Repository Scanner
# ============================================================

def scan_repository(
    repository_path: str
) -> list[str]:
    """
    Scan a repository and return all supported source files.
    """

    repository_path = normalize_path(
        repository_path
    )

    if not os.path.exists(repository_path):
        raise ValueError(
            f"Repository does not exist: "
            f"{repository_path}"
        )

    if not os.path.isdir(repository_path):
        raise ValueError(
            f"Repository path is not a directory: "
            f"{repository_path}"
        )

    files = []

    for root, directories, filenames in os.walk(
        repository_path
    ):
        # Prevent traversal into ignored directories
        directories[:] = [
            directory
            for directory in directories
            if directory not in IGNORED_DIRECTORIES
        ]

        for filename in filenames:
            extension = os.path.splitext(
                filename
            )[1].lower()

            if extension not in SUPPORTED_EXTENSIONS:
                continue

            file_path = os.path.join(
                root,
                filename
            )

            files.append(
                normalize_path(file_path)
            )

    # Stable ordering makes indexing deterministic
    files.sort()

    return files


# ============================================================
# File Reader
# ============================================================

def read_file(
    file_path: str
) -> str:
    """
    Read a source file using UTF-8.

    errors='replace' prevents one malformed byte
    from crashing the entire repository indexing process.
    """

    try:
        with open(
            file_path,
            "r",
            encoding="utf-8",
            errors="replace"
        ) as file:
            return file.read()

    except OSError as e:
        raise ValueError(
            f"Failed to read file "
            f"{file_path}: {e}"
        )


# ============================================================
# File Metadata
# ============================================================

def get_file_metadata(
    file_path: str,
    repository_path: str | None = None
) -> dict:
    """
    Generate standardized metadata for a repository file.

    Metadata includes:
        filename
        file_path
        relative_path
        language
        extension
        repository_path
    """

    file_path = normalize_path(
        file_path
    )

    filename = os.path.basename(
        file_path
    )

    extension = os.path.splitext(
        filename
    )[1].lower()

    language = LANGUAGE_MAP.get(
        extension,
        "unknown"
    )

    metadata = {
        "file_path": file_path,
        "filename": filename,
        "relative_path": "",
        "language": language,
        "extension": extension,
        "repository_path": ""
    }

    if repository_path:
        repository_path = normalize_path(
            repository_path
        )

        metadata["repository_path"] = (
            repository_path
        )

        metadata["relative_path"] = (
            get_relative_path(
                file_path,
                repository_path
            )
        )

    return metadata


# ============================================================
# Document Creation
# ============================================================

def create_document(
    file_path: str,
    repository_path: str | None = None
) -> dict:
    """
    Create a document containing file content
    and standardized metadata.
    """

    metadata = get_file_metadata(
        file_path,
        repository_path
    )

    content = read_file(
        file_path
    )

    return {
        "content": content,
        "metadata": metadata
    }


# ============================================================
# Load Repository
# ============================================================

def load_repository(
    repository_path: str
) -> list[dict]:
    """
    Scan and load all supported repository files.
    """

    repository_path = normalize_path(
        repository_path
    )

    files = scan_repository(
        repository_path
    )

    documents = []

    for file_path in files:
        try:
            document = create_document(
                file_path,
                repository_path
            )

            documents.append(
                document
            )

        except ValueError as e:
            print(
                f"Skipping file: {e}"
            )

    return documents


# ============================================================
# Manual Test
# ============================================================

if __name__ == "__main__":

    repository_path = (
        "data/monetrik-financesystem"
    )

    documents = load_repository(
        repository_path
    )

    print(
        f"Total documents: {len(documents)}"
    )

    if documents:
        print(
            "\n--- First Document ---\n"
        )

        print(
            documents[0]
        )