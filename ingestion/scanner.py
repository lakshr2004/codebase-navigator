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
    """
    Normalize a filesystem path.
    Consistently handles Windows and POSIX separators.
    """
    if not file_path:
        return ""
    return os.path.normpath(os.path.abspath(file_path))


def get_relative_path(
    file_path: str,
    repository_path: str
) -> str:
    """
    Return a repository-relative path with forward slashes '/'.
    """
    absolute_file = normalize_path(file_path)
    absolute_repository = normalize_path(repository_path)

    relative_path = os.path.relpath(
        absolute_file,
        absolute_repository
    )

    return relative_path.replace("\\", "/")


def is_binary_file(file_path: str) -> bool:
    """
    Check if a file is a binary file based on extension or quick chunk inspection.
    """
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
    """
    Check if a file should be scanned and indexed.
    """
    filename = os.path.basename(file_path).lower()
    if filename in SUPPORTED_FILENAMES:
        return True

    extension = os.path.splitext(filename)[1].lower()
    if extension in BINARY_EXTENSIONS:
        return False

    return extension in SUPPORTED_EXTENSIONS


def get_file_language(file_path: str) -> str:
    """
    Determine the programming or markup language of a file.
    """
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

def get_repository_files(
    repository_path: str
) -> list[str]:
    """
    Canonical repository file scanner.
    Returns relative paths (using '/') of all supported source/doc files,
    ignoring .git, node_modules, virtualenvs, build dirs, and binary files.
    """
    repository_path = normalize_path(repository_path)

    if not os.path.isdir(repository_path):
        return []

    files = []

    for root, directories, filenames in os.walk(repository_path):
        # Prevent traversal into ignored directories
        directories[:] = [
            directory
            for directory in directories
            if directory not in IGNORED_DIRECTORIES
            and not directory.startswith(".git")
        ]

        for filename in filenames:
            absolute_path = os.path.join(root, filename)

            if not is_supported_file(filename):
                continue

            if is_binary_file(absolute_path):
                continue

            relative_path = os.path.relpath(absolute_path, repository_path)
            files.append(relative_path.replace("\\", "/"))

    return sorted(files)


def get_repository_folders(
    repository_path: str
) -> list[str]:
    """
    Returns relative directory paths (using '/') excluding ignored directories.
    """
    repository_path = normalize_path(repository_path)

    if not os.path.isdir(repository_path):
        return []

    folders = set()

    for root, directories, _ in os.walk(repository_path):
        directories[:] = [
            directory
            for directory in directories
            if directory not in IGNORED_DIRECTORIES
            and not directory.startswith(".git")
        ]

        for directory in directories:
            absolute_path = os.path.join(root, directory)
            relative_path = os.path.relpath(absolute_path, repository_path)
            folders.add(relative_path.replace("\\", "/"))

    return sorted(folders)


def scan_repository(
    repository_path: str
) -> list[str]:
    """
    Scan a repository and return absolute paths of all supported source files.
    """
    repository_path = normalize_path(repository_path)

    if not os.path.exists(repository_path):
        raise ValueError(
            f"Repository does not exist: {repository_path}"
        )

    if not os.path.isdir(repository_path):
        raise ValueError(
            f"Repository path is not a directory: {repository_path}"
        )

    rel_files = get_repository_files(repository_path)
    files = [
        normalize_path(os.path.join(repository_path, f.replace("/", os.sep)))
        for f in rel_files
    ]

    return sorted(files)


# ============================================================
# File Reader
# ============================================================

def read_file(
    file_path: str
) -> str:
    """
    Read a source file using UTF-8 with errors='replace'.
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
            f"Failed to read file {file_path}: {e}"
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
    """
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
        metadata["relative_path"] = get_relative_path(
            file_path,
            repository_path
        )

    return metadata


# ============================================================
# Document Creation & Loading
# ============================================================

def create_document(
    file_path: str,
    repository_path: str | None = None
) -> dict:
    """
    Create a document containing file content and standardized metadata.
    """
    metadata = get_file_metadata(
        file_path,
        repository_path
    )
    content = read_file(file_path)

    return {
        "content": content,
        "metadata": metadata
    }


def load_repository(
    repository_path: str
) -> list[dict]:
    """
    Scan and load all supported repository files.
    """
    repository_path = normalize_path(repository_path)
    files = scan_repository(repository_path)
    documents = []

    for file_path in files:
        try:
            document = create_document(
                file_path,
                repository_path
            )
            documents.append(document)
        except ValueError as e:
            print(f"Skipping file: {e}")

    return documents