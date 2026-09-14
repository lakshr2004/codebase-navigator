import os
import re
import sys

sys.path.append(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

from rag.vector_store import (
    client,
    get_collection_name
)

from rag.embeddings import generate_embedding
from rag.generator import generate_answer


# ============================================================
# Configuration
# ============================================================

SIMILARITY_THRESHOLD = 0.05

DEFAULT_LIMIT = 10

IGNORED_DIRECTORIES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
}


# ============================================================
# Path Utilities
# ============================================================

def normalize_path(file_path: str) -> str:
    """
    Normalize a filesystem path so Windows path
    variations are treated consistently.
    """

    if not file_path:
        return ""

    return os.path.normcase(
        os.path.normpath(
            str(file_path)
        )
    )


def clean_source_path(
    file_path: str,
    repository_path: str
) -> str:
    """
    Convert an absolute repository path into a
    repository-relative path.
    """

    if not file_path:
        return ""

    normalized_file = normalize_path(
        file_path
    )

    normalized_repo = normalize_path(
        repository_path
    )

    try:
        relative_path = os.path.relpath(
            normalized_file,
            normalized_repo
        )

        if relative_path != ".." and not relative_path.startswith(
            ".." + os.sep
        ):
            return relative_path.replace(
                "\\",
                "/"
            )

    except ValueError:
        pass

    return str(file_path).replace(
        "\\",
        "/"
    )


# ============================================================
# Repository File Discovery
# ============================================================

def get_repository_files(
    repository_path: str
) -> list[str]:
    """
    Return all files inside the repository as
    repository-relative paths.

    This is filesystem-based rather than vector-based
    because repository structure questions require
    complete and deterministic knowledge.
    """

    if not os.path.isdir(
        repository_path
    ):
        return []

    files = []

    for root, directories, filenames in os.walk(
        repository_path
    ):

        directories[:] = [
            directory
            for directory in directories
            if directory not in IGNORED_DIRECTORIES
        ]

        for filename in filenames:

            absolute_path = os.path.join(
                root,
                filename
            )

            relative_path = os.path.relpath(
                absolute_path,
                repository_path
            )

            files.append(
                relative_path.replace(
                    "\\",
                    "/"
                )
            )

    return sorted(files)


def get_repository_folders(
    repository_path: str
) -> list[str]:
    """
    Return all folders inside the repository
    as repository-relative paths.
    """

    if not os.path.isdir(
        repository_path
    ):
        return []

    folders = set()

    for root, directories, _ in os.walk(
        repository_path
    ):

        directories[:] = [
            directory
            for directory in directories
            if directory not in IGNORED_DIRECTORIES
        ]

        for directory in directories:

            absolute_path = os.path.join(
                root,
                directory
            )

            relative_path = os.path.relpath(
                absolute_path,
                repository_path
            )

            folders.add(
                relative_path.replace(
                    "\\",
                    "/"
                )
            )

    return sorted(folders)


# ============================================================
# File Type Utilities
# ============================================================

EXTENSION_LANGUAGE_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".java": "java",
    ".cpp": "cpp",
    ".c": "c",
    ".go": "go",
    ".rs": "rust",
    ".html": "html",
    ".htm": "html",
    ".css": "css",
    ".scss": "scss",
    ".sass": "sass",
    ".less": "less",
    ".json": "json",
    ".md": "markdown",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".sh": "shell",
    ".sql": "sql",
    ".toml": "toml",
    ".xml": "xml",
}


LANGUAGE_EXTENSION_MAP = {
    "python": {".py"},
    "javascript": {".js", ".jsx"},
    "js": {".js", ".jsx"},
    "typescript": {".ts", ".tsx"},
    "ts": {".ts", ".tsx"},
    "java": {".java"},
    "cpp": {".cpp"},
    "c": {".c"},
    "go": {".go"},
    "rust": {".rs"},
    "html": {".html", ".htm"},
    "css": {".css"},
    "scss": {".scss"},
    "sass": {".sass"},
    "less": {".less"},
    "json": {".json"},
    "markdown": {".md"},
    "md": {".md"},
    "yaml": {".yaml", ".yml"},
    "yml": {".yaml", ".yml"},
    "shell": {".sh"},
    "sql": {".sql"},
    "toml": {".toml"},
    "xml": {".xml"},
}


def get_file_language(
    file_path: str
) -> str:
    """
    Return a normalized language name based on extension.
    """

    extension = os.path.splitext(
        file_path
    )[1].lower()

    return EXTENSION_LANGUAGE_MAP.get(
        extension,
        "unknown"
    )


# ============================================================
# Query Classification
# ============================================================

def is_repository_file_query(
    query: str
) -> bool:
    """
    Detect generic repository file-list questions.
    """

    query_lower = query.lower().strip()

    patterns = [
        "what files are in the repository",
        "what files are in repository",
        "list files",
        "list all files",
        "show all files",
        "show files",
        "which files are in the repository",
        "which files are in repository",
        "files in the repository",
        "files in repository",
        "repository files",
        "project files",
        "list repository files",
        "list project files",
        "what is in the repository",
        "what is inside the repository",
        "show repository files",
        "show project files",
    ]

    return any(
        pattern in query_lower
        for pattern in patterns
    )


def is_repository_structure_query(
    query: str
) -> bool:
    """
    Detect repository folder / structure questions.
    """

    query_lower = query.lower().strip()

    patterns = [
        "repository structure",
        "project structure",
        "show repository structure",
        "show project structure",
        "folder structure",
        "directory structure",
        "what folders are present",
        "what folders are there",
        "list folders",
        "list all folders",
        "show folders",
        "show all folders",
        "which folders are present",
        "which folders are there",
        "directories in repository",
        "directories in the repository",
    ]

    return any(
        pattern in query_lower
        for pattern in patterns
    )


def detect_language_filter(
    query: str
):
    """
    Detect language/type-specific repository queries.

    Examples:
        What JavaScript files exist?
        List HTML files.
        What CSS files are there?
    """

    query_lower = query.lower()

    language_aliases = {
        "javascript": "javascript",
        "js": "javascript",
        "typescript": "typescript",
        "ts": "typescript",
        "python": "python",
        "py": "python",
        "java": "java",
        "cpp": "cpp",
        "c++": "cpp",
        "rust": "rust",
        "go": "go",
        "html": "html",
        "css": "css",
        "scss": "scss",
        "sass": "sass",
        "json": "json",
        "markdown": "markdown",
        "md": "markdown",
        "yaml": "yaml",
        "yml": "yaml",
        "shell": "shell",
        "sql": "sql",
        "toml": "toml",
        "xml": "xml",
    }

    listing_words = [
        "files",
        "file",
        "exist",
        "exists",
        "present",
        "available",
        "contain",
        "contains",
        "list",
        "show",
        "which",
        "what",
    ]

    has_listing_intent = any(
        word in query_lower
        for word in listing_words
    )

    if not has_listing_intent:
        return None

    for alias, language in language_aliases.items():

        pattern = rf"\b{re.escape(alias)}\b"

        if re.search(
            pattern,
            query_lower
        ):
            return language

    return None


def is_file_location_query(
    query: str
) -> bool:
    """
    Detect exact file location/path questions.
    """

    query_lower = query.lower().strip()

    patterns = [
        "where is",
        "where can i find",
        "which folder contains",
        "which directory contains",
        "what is the path of",
        "what's the path of",
        "path of",
        "location of",
        "located",
        "find the file",
        "find file",
    ]

    return any(
        pattern in query_lower
        for pattern in patterns
    )


# ============================================================
# Extract File Name From Query
# ============================================================

def extract_filename_candidates(
    query: str
) -> list[str]:
    """
    Extract likely filenames from a user query.

    Handles examples such as:
        srcipt.js
        index.html
        style.css
        app.py
    """

    candidates = []

    # Normal filename with extension
    extension_pattern = re.compile(
        r"\b[\w.\-]+\.(?:"
        r"py|js|jsx|ts|tsx|java|cpp|c|go|rs|"
        r"html?|css|scss|sass|less|json|md|"
        r"yaml|yml|sh|sql|toml|xml"
        r")\b",
        re.IGNORECASE
    )

    for match in extension_pattern.findall(
        query
    ):
        if match not in candidates:
            candidates.append(match)

    return candidates


# ============================================================
# Deterministic File Location
# ============================================================

def find_file_location(
    query: str,
    repository_path: str
):
    """
    Deterministically locate a file in the repository.

    Returns:
        {
            "answer": "...",
            "sources": [...]
        }

    or None when no exact file can be resolved.
    """

    files = get_repository_files(
        repository_path
    )

    if not files:
        return None

    candidates = extract_filename_candidates(
        query
    )

    if not candidates:
        return None

    for candidate in candidates:

        candidate_lower = candidate.lower()

        exact_matches = [
            file_path
            for file_path in files
            if os.path.basename(
                file_path
            ).lower() == candidate_lower
        ]

        if not exact_matches:
            continue

        if len(exact_matches) == 1:

            file_path = exact_matches[0]

            return {
                "answer": (
                    f"The file `{candidate}` is located at "
                    f"`{file_path}`."
                ),
                "sources": [
                    {
                        "file": file_path,
                        "language": get_file_language(
                            file_path
                        ),
                        "start_line": None,
                        "end_line": None,
                        "score": 1.0,
                    }
                ]
            }

        # Multiple files with same filename
        file_lines = "\n".join(
            f"- `{file_path}`"
            for file_path in exact_matches
        )

        return {
            "answer": (
                f"I found multiple files named "
                f"`{candidate}`:\n\n"
                f"{file_lines}"
            ),
            "sources": [
                {
                    "file": file_path,
                    "language": get_file_language(
                        file_path
                    ),
                    "start_line": None,
                    "end_line": None,
                    "score": 1.0,
                }
                for file_path in exact_matches
            ]
        }

    return None


# ============================================================
# Repository File Answers
# ============================================================

def build_repository_file_answer(
    repository_path: str,
    language_filter: str | None = None
):
    """
    Build deterministic file-list response.
    """

    files = get_repository_files(
        repository_path
    )

    if language_filter:
        extensions = LANGUAGE_EXTENSION_MAP.get(
            language_filter,
            set()
        )

        files = [
            file_path
            for file_path in files
            if os.path.splitext(
                file_path
            )[1].lower() in extensions
        ]

    if not files:

        if language_filter:
            return {
                "answer": (
                    f"I couldn't find any "
                    f"{language_filter} files in the repository."
                ),
                "sources": []
            }

        return {
            "answer": (
                "I couldn't find any files in the repository."
            ),
            "sources": []
        }

    file_lines = "\n".join(
        f"- `{file_path}`"
        for file_path in files
    )

    if language_filter:

        answer = (
            f"The repository contains "
            f"{len(files)} {language_filter} "
            f"file(s):\n\n"
            f"{file_lines}"
        )

    else:

        answer = (
            f"The repository contains "
            f"{len(files)} files:\n\n"
            f"{file_lines}"
        )

    sources = [
        {
            "file": file_path,
            "language": get_file_language(
                file_path
            ),
            "start_line": None,
            "end_line": None,
            "score": 1.0,
        }
        for file_path in files
    ]

    return {
        "answer": answer,
        "sources": sources
    }


# ============================================================
# Repository Structure Answer
# ============================================================

def build_repository_structure_answer(
    repository_path: str
):
    """
    Build deterministic repository folder structure response.
    """

    files = get_repository_files(
        repository_path
    )

    folders = get_repository_folders(
        repository_path
    )

    if not files and not folders:
        return {
            "answer": (
                "I couldn't find any files or folders "
                "in the repository."
            ),
            "sources": []
        }

    lines = []

    if folders:

        lines.append("Folders:")

        for folder in folders:
            lines.append(
                f"- `{folder}/`"
            )

        lines.append("")

    if files:

        lines.append("Files:")

        for file_path in files:
            lines.append(
                f"- `{file_path}`"
            )

    answer = "\n".join(
        lines
    )

    sources = [
        {
            "file": file_path,
            "language": get_file_language(
                file_path
            ),
            "start_line": None,
            "end_line": None,
            "score": 1.0,
        }
        for file_path in files
    ]

    return {
        "answer": answer,
        "sources": sources
    }


# ============================================================
# Retrieval Result Processing
# ============================================================

def deduplicate_results(
    results
):
    """
    Remove duplicate chunks while keeping the
    highest-scoring result.
    """

    unique_results = {}

    for result in results:

        payload = result.payload or {}

        if not payload:
            continue

        metadata = payload.get(
            "metadata",
            {}
        )

        file_path = metadata.get(
            "file_path",
            ""
        )

        start_line = metadata.get(
            "start_line"
        )

        end_line = metadata.get(
            "end_line"
        )

        key = (
            normalize_path(file_path),
            start_line,
            end_line
        )

        if (
            key not in unique_results
            or result.score > unique_results[
                key
            ].score
        ):
            unique_results[key] = result

    return sorted(
        unique_results.values(),
        key=lambda result: result.score,
        reverse=True
    )


def diversify_results(
    results,
    max_per_file=3
):
    """
    Prevent one file from completely dominating
    the final context.
    """

    selected_results = []
    file_counts = {}

    for result in results:

        payload = result.payload or {}

        if not payload:
            continue

        metadata = payload.get(
            "metadata",
            {}
        )

        file_path = metadata.get(
            "file_path",
            ""
        )

        normalized_path = normalize_path(
            file_path
        )

        current_count = file_counts.get(
            normalized_path,
            0
        )

        if current_count >= max_per_file:
            continue

        selected_results.append(
            result
        )

        file_counts[
            normalized_path
        ] = current_count + 1

    return selected_results


# ============================================================
# Query Tokenization
# ============================================================

def extract_query_tokens(
    query: str
) -> list[str]:
    """
    Extract useful search tokens from a query.

    Keeps identifiers such as:
        increaseScore
        runTimer
        getNewHit
        pannel-bottom
    """

    tokens = re.findall(
    r"#?[A-Za-z_][A-Za-z0-9_\-\.]*",
    query
)

    stop_words = {
        "where",
        "what",
        "which",
        "how",
        "does",
        "do",
        "is",
        "are",
        "the",
        "a",
        "an",
        "in",
        "of",
        "to",
        "for",
        "on",
        "with",
        "and",
        "or",
        "me",
        "show",
        "find",
        "tell",
        "about",
        "work",
        "works",
        "used",
        "use",
        "this",
        "that",
        "code",
        "file",
        "files",
    }

    useful_tokens = []

    for token in tokens:

        normalized = token.lower()

        if normalized in stop_words:
            continue

        if len(normalized) < 2:
            continue

        if normalized not in useful_tokens:
            useful_tokens.append(
                normalized
            )

    return useful_tokens


# ============================================================
# Hybrid Keyword Ranking
# ============================================================

def keyword_matches(
    query: str,
    result
) -> float:
    """
    Calculate keyword relevance from:

        1. filename
        2. relative path
        3. absolute path
        4. chunk content
        5. exact identifiers

    This fixes the previous issue where only filename/path
    were searched.
    """

    query_lower = query.lower()

    payload = result.payload or {}

    metadata = payload.get(
        "metadata",
        {}
    )

    filename = str(
        metadata.get(
            "filename",
            ""
        )
    ).lower()

    file_path = str(
        metadata.get(
            "file_path",
            ""
        )
    ).lower()

    relative_path = str(
        metadata.get(
            "relative_path",
            ""
        )
    ).lower()

    content = str(
        payload.get(
            "content",
            ""
        )
    ).lower()

    score = 0.0

    # --------------------------------------------------------
    # Exact filename
    # --------------------------------------------------------

    if filename and filename in query_lower:
        score += 100.0

    # --------------------------------------------------------
    # Exact relative path
    # --------------------------------------------------------

    if (
        relative_path
        and relative_path in query_lower
    ):
        score += 90.0

    # --------------------------------------------------------
    # Exact absolute path
    # --------------------------------------------------------

    if (
        file_path
        and file_path in query_lower
    ):
        score += 80.0

    # --------------------------------------------------------
    # Filename without extension
    # --------------------------------------------------------

    filename_without_extension = os.path.splitext(
        filename
    )[0]

    if (
        filename_without_extension
        and filename_without_extension in query_lower
    ):
        score += 50.0

    # --------------------------------------------------------
    # Content / identifier matching
    # --------------------------------------------------------

    tokens = extract_query_tokens(
        query
    )

    for token in tokens:

        # Exact token in content
        if token in content:

            # Longer identifiers are generally more specific.
            if len(token) >= 8:
                score += 30.0
            elif len(token) >= 5:
                score += 20.0
            else:
                score += 10.0

        # Token in filename
        if token in filename:
            score += 15.0

        # Token in relative path
        if token in relative_path:
            score += 10.0

    return score


# ============================================================
# Exact Content Search
# ============================================================

def content_match_score(
    query: str,
    result
) -> int:
    """
    Count useful query tokens appearing in chunk content.
    """

    payload = result.payload or {}

    content = str(
        payload.get(
            "content",
            ""
        )
    ).lower()

    if not content:
        return 0

    tokens = extract_query_tokens(
        query
    )

    return sum(
        1
        for token in tokens
        if token in content
    )


# ============================================================
# Semantic + Hybrid Search
# ============================================================

def search_code(
    query: str,
    repository_path: str,
    limit: int = DEFAULT_LIMIT
):
    """
    Search indexed repository using:

        semantic similarity
        +
        metadata keyword matching
        +
        exact code/content matching
    """

    if not query or not query.strip():
        return []

    if not os.path.isdir(
        repository_path
    ):
        raise ValueError(
            f"Repository does not exist: "
            f"{repository_path}"
        )

    collection_name = get_collection_name(
        repository_path
    )

    if not client.collection_exists(
        collection_name
    ):
        raise ValueError(
            f"Repository is not indexed: "
            f"{repository_path}"
        )

    # ========================================================
    # 1. Semantic Retrieval
    # ========================================================

    query_vector = generate_embedding(
        query
    )

    retrieval_limit = max(
        limit * 5,
        30
    )

    results = client.query_points(
        collection_name=collection_name,
        query=query_vector,
        limit=retrieval_limit
    ).points

    # ========================================================
    # 2. Filter weak semantic matches
    # ========================================================

    relevant_results = [
        result
        for result in results
        if result.score >= SIMILARITY_THRESHOLD
    ]

    # ========================================================
    # 3. Hybrid Ranking
    # ========================================================

    ranked_results = []

    for result in relevant_results:

        semantic_score = float(
            result.score
        )

        keyword_score = keyword_matches(
            query,
            result
        )

        exact_content_matches = content_match_score(
            query,
            result
        )

        # Semantic score remains important.
        #
        # Keyword score is deliberately scaled down so
        # keyword matches enhance semantic retrieval instead
        # of completely replacing it.
        #
        # Exact content matches receive an additional boost.

        final_score = (
            semantic_score
            + (keyword_score * 0.01)
            + (exact_content_matches * 0.08)
        )

        ranked_results.append(
            (
                final_score,
                result
            )
        )

    ranked_results.sort(
        key=lambda item: item[0],
        reverse=True
    )

    ranked_results = [
        result
        for _, result in ranked_results
    ]

    # ========================================================
    # 4. Deduplicate
    # ========================================================

    unique_results = deduplicate_results(
        ranked_results
    )

    # ========================================================
    # 5. Determine whether query targets a file
    # ========================================================

    filename_candidates = extract_filename_candidates(
        query
    )

    targeted_file = bool(
        filename_candidates
    )

    # ========================================================
    # 6. Diversification
    # ========================================================

    if targeted_file:

        # If user explicitly mentions a file, allow more
        # chunks from that file because they are likely
        # relevant.
        diversified_results = diversify_results(
            unique_results,
            max_per_file=6
        )

    else:

        diversified_results = diversify_results(
            unique_results,
            max_per_file=3
        )

    return diversified_results[:limit]


# ============================================================
# Context Construction
# ============================================================

def build_context(
    results,
    repository_path: str
):
    """
    Convert retrieval results into LLM context.
    """

    context_parts = []
    sources = []

    for result in results:

        payload = result.payload or {}

        if not payload:
            continue

        metadata = payload.get(
            "metadata",
            {}
        )

        content = payload.get(
            "content",
            ""
        )

        if not content:
            continue

        file_path = metadata.get(
            "relative_path"
        )

        if not file_path:

            file_path = metadata.get(
                "file_path",
                "Unknown file"
            )

            file_path = clean_source_path(
                file_path,
                repository_path
            )

        language = metadata.get(
            "language",
            "unknown"
        )

        start_line = metadata.get(
            "start_line"
        )

        end_line = metadata.get(
            "end_line"
        )

        context_parts.append(
            f"""
File: {file_path}

Language: {language}

Lines: {start_line} - {end_line}

Code:

{content}
"""
        )

        sources.append(
            {
                "file": file_path,
                "language": language,
                "start_line": start_line,
                "end_line": end_line,
                "score": result.score,
            }
        )

    return (
        "\n".join(context_parts),
        sources
    )


# ============================================================
# Main Answer Function
# ============================================================

def answer_query(
    query: str,
    repository_path: str,
    limit: int = DEFAULT_LIMIT
):
    """
    Main retrieval + answer pipeline.

    Deterministic repository/file operations happen first.
    Semantic RAG is used only for actual code understanding.
    """

    # ========================================================
    # Validation
    # ========================================================

    if not query or not query.strip():

        return {
            "answer": "Please provide a question.",
            "sources": []
        }

    query = query.strip()

    if not repository_path:

        return {
            "answer": "Repository path is required.",
            "sources": []
        }

    if not os.path.isdir(
        repository_path
    ):

        return {
            "answer": (
                f"The repository does not exist: "
                f"`{repository_path}`"
            ),
            "sources": []
        }

    # ========================================================
    # 1. Repository Structure Query
    # ========================================================

    if is_repository_structure_query(
        query
    ):

        return build_repository_structure_answer(
            repository_path
        )

    # ========================================================
    # 2. Language-Specific File Query
    # ========================================================

    language_filter = detect_language_filter(
        query
    )

    if language_filter:

        return build_repository_file_answer(
            repository_path,
            language_filter
        )

    # ========================================================
    # 3. Generic Repository File Query
    # ========================================================

    if is_repository_file_query(
        query
    ):

        return build_repository_file_answer(
            repository_path
        )

    # ========================================================
    # 4. Exact File Location Query
    # ========================================================

    if is_file_location_query(
        query
    ):

        location_result = find_file_location(
            query,
            repository_path
        )

        if location_result:

            return location_result

    # ========================================================
    # 5. Normal RAG Search
    # ========================================================

    try:

        results = search_code(
            query=query,
            repository_path=repository_path,
            limit=limit
        )

    except ValueError as error:

        return {
            "answer": str(error),
            "sources": []
        }

    # ========================================================
    # 6. No Retrieval Results
    # ========================================================

    if not results:

        return {
            "answer": (
                "I couldn't find enough relevant "
                "information in the codebase."
            ),
            "sources": []
        }

    # ========================================================
    # 7. Build Context
    # ========================================================

    context, sources = build_context(
        results,
        repository_path
    )

    if not context.strip():

        return {
            "answer": (
                "I couldn't find enough relevant "
                "information in the codebase."
            ),
            "sources": []
        }

    # ========================================================
    # 8. Generate Answer
    # ========================================================

    answer = generate_answer(
        query,
        context
    )

    return {
        "answer": answer,
        "sources": sources
    }


# ============================================================
# Manual Testing
# ============================================================

if __name__ == "__main__":

    repository_path = (
        "data/monetrik-financesystem"
    )

    test_queries = [
        "What files are in the repository?",
        "What folders are present?",
        "What JavaScript files exist?",
        "What HTML files exist?",
        "What CSS files exist?",
        "Where is srcipt.js located?",
        "Where is index.html?",
        "What does srcipt.js do?",
        "Where is increaseScore defined?",
        "Where is runTimer defined?",
        "Find all usages of getNewHit",
        "Where is #pannel-bottom used?",
    ]

    for query in test_queries:

        print(
            "\n"
            + "=" * 70
        )

        print(
            "QUERY:",
            query
        )

        print(
            "=" * 70
        )

        result = answer_query(
            query,
            repository_path
        )

        print(
            "\nANSWER:\n"
        )

        print(
            result["answer"]
        )

        print(
            "\nSOURCES:\n"
        )

        for source in result["sources"]:

            print(
                source
            )