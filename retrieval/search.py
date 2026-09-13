import os
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

# Minimum similarity score for semantic retrieval
SIMILARITY_THRESHOLD = 0.05


# ============================================================
# Path Utilities
# ============================================================

def normalize_path(file_path: str) -> str:
    """
    Normalize file paths so Windows path variations
    are treated as the same path.
    """

    return os.path.normcase(
        os.path.normpath(file_path)
    )


def clean_source_path(
    file_path: str,
    repository_path: str
) -> str:
    """
    Convert an absolute repository path into a
    repository-relative path.
    """

    normalized_file = normalize_path(file_path)
    normalized_repo = normalize_path(repository_path)

    if normalized_file.startswith(normalized_repo):

        relative_path = normalized_file[
            len(normalized_repo):
        ].lstrip("\\/")

        return relative_path.replace("\\", "/")

    return normalized_file.replace("\\", "/")


# ============================================================
# Repository File Discovery
# ============================================================

def get_repository_files(repository_path: str):
    """
    Return all files inside the repository as
    repository-relative paths.

    This is intentionally filesystem-based rather than
    semantic-retrieval-based because questions such as:

        What files are in the repository?
        List all files.
        Show me the repository structure.

    require complete repository knowledge.
    """

    if not os.path.isdir(repository_path):
        return []

    files = []

    for root, dirs, filenames in os.walk(repository_path):

        # Ignore common directories that should not be treated
        # as source files of the repository.
        dirs[:] = [
            directory
            for directory in dirs
            if directory not in {
                ".git",
                ".venv",
                "venv",
                "__pycache__",
                "node_modules"
            }
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
                relative_path.replace("\\", "/")
            )

    return sorted(files)


def is_repository_file_query(query: str) -> bool:
    """
    Detect questions asking for the repository's
    file list / structure rather than code semantics.
    """

    query_lower = query.lower().strip()

    file_query_patterns = [
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
        "repository structure",
        "project structure",
        "show repository structure",
        "show project structure",
        "list repository files",
        "list project files",
        "what is in the repository"
    ]

    return any(
        pattern in query_lower
        for pattern in file_query_patterns
    )


def build_repository_file_answer(
    repository_path: str
):
    """
    Build a deterministic answer for repository file-list
    queries.
    """

    files = get_repository_files(
        repository_path
    )

    if not files:
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

    answer = (
        f"The repository contains {len(files)} files:\n\n"
        f"{file_lines}"
    )

    sources = [
        {
            "file": file_path,
            "language": (
                os.path.splitext(file_path)[1]
                .lstrip(".")
                or "unknown"
            ),
            "start_line": None,
            "end_line": None,
            "score": 1.0
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

def deduplicate_results(results):
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
            or result.score > unique_results[key].score
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
    Prevent a single file from dominating
    the final retrieval context.
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

        file_counts[normalized_path] = (
            current_count + 1
        )

    return selected_results


# ============================================================
# Keyword Ranking
# ============================================================

def keyword_matches(
    query: str,
    result
) -> int:
    """
    Calculate a lightweight keyword relevance score
    using indexed metadata.

    This helps exact file-name queries such as:

        Where is srcipt.js located?
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

    score = 0

    # Exact filename mentioned in query
    if filename and filename in query_lower:
        score += 100

    # Exact path mentioned in query
    if file_path and file_path in query_lower:
        score += 80

    # Filename without extension
    filename_without_extension = os.path.splitext(
        filename
    )[0]

    if (
        filename_without_extension
        and filename_without_extension in query_lower
    ):
        score += 50

    return score


# ============================================================
# Semantic + Hybrid Search
# ============================================================

def search_code(
    query: str,
    repository_path: str,
    limit: int = 10
):
    """
    Search the indexed repository using a hybrid
    keyword + semantic retrieval strategy.
    """

    collection_name = get_collection_name(
        repository_path
    )

    # Check whether repository is indexed
    if not client.collection_exists(
        collection_name
    ):
        raise ValueError(
            f"Repository is not indexed: "
            f"{repository_path}"
        )

    # --------------------------------------------------------
    # 1. Semantic retrieval
    # --------------------------------------------------------

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

    print(
        "\n========== RETRIEVAL DEBUG =========="
    )

    print(
        "QUERY:",
        query
    )

    print(
        "COLLECTION:",
        collection_name
    )

    print(
        "RAW RESULTS:",
        len(results)
    )

    for result in results[:10]:

        payload = result.payload or {}

        metadata = payload.get(
            "metadata",
            {}
        )

        print(
            "\nSCORE:",
            result.score
        )

        print(
            "FILE:",
            metadata.get("file_path")
        )

        print(
            "LINES:",
            metadata.get("start_line"),
            "-",
            metadata.get("end_line")
        )

        print(
            "CONTENT:"
        )

        print(
            payload.get(
                "content",
                ""
            )[:1000]
        )

    print(
        "====================================\n"
    )

    # --------------------------------------------------------
    # 2. Remove extremely weak semantic matches
    # --------------------------------------------------------

    relevant_results = [
        result
        for result in results
        if result.score >= SIMILARITY_THRESHOLD
    ]

    # --------------------------------------------------------
    # 3. Hybrid ranking
    # --------------------------------------------------------

    ranked_results = []

    for result in relevant_results:

        keyword_score = keyword_matches(
            query,
            result
        )

        final_score = (
            result.score
            + keyword_score
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

    # --------------------------------------------------------
    # 4. Deduplicate
    # --------------------------------------------------------

    unique_results = deduplicate_results(
        ranked_results
    )

    # --------------------------------------------------------
    # 5. Diversify files
    # --------------------------------------------------------

    diversified_results = diversify_results(
        unique_results,
        max_per_file=3
    )

    return diversified_results[:limit]


# ============================================================
# Answer Query
# ============================================================

def answer_query(
    query: str,
    repository_path: str,
    limit: int = 10
):
    """
    Retrieve relevant code and generate
    an AI answer.

    Special repository-level queries are handled
    deterministically before semantic retrieval.
    """

    # ========================================================
    # SPECIAL CASE:
    # Repository file listing
    # ========================================================

    if is_repository_file_query(
        query
    ):

        print(
            "\n========== REPOSITORY FILE QUERY =========="
        )

        print(
            "QUERY:",
            query
        )

        print(
            "REPOSITORY:",
            repository_path
        )

        repository_files = get_repository_files(
            repository_path
        )

        print(
            "FILES FOUND:",
            len(repository_files)
        )

        for file_path in repository_files:
            print(
                " -",
                file_path
            )

        print(
            "===========================================\n"
        )

        return build_repository_file_answer(
            repository_path
        )

    # ========================================================
    # NORMAL RAG QUERY
    # ========================================================

    results = search_code(
        query=query,
        repository_path=repository_path,
        limit=limit
    )

    # Nothing relevant found
    if not results:

        return {
            "answer": (
                "I couldn't find enough relevant "
                "information in the codebase."
            ),
            "sources": []
        }

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

        file_path = metadata.get(
            "file_path",
            "Unknown file"
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

        # ----------------------------------------------------
        # Convert absolute path to relative path
        # ----------------------------------------------------

        file_path = clean_source_path(
            file_path,
            repository_path
        )

        # ----------------------------------------------------
        # Context sent to LLM
        # ----------------------------------------------------

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
                "score": result.score
            }
        )

    context = "\n".join(
        context_parts
    )

    print(
        "\n========== GENERATOR DEBUG =========="
    )

    print(
        "QUERY:",
        query
    )

    print(
        "CONTEXT LENGTH:",
        len(context)
    )

    print(
        "CONTEXT:"
    )

    print(
        context
    )

    print(
        "====================================\n"
    )

    # ========================================================
    # Generate answer
    # ========================================================

    answer = generate_answer(
        query,
        context
    )

    print(
        "\n========== LLM CONTEXT =========="
    )

    print(
        context
    )

    print(
        "=================================\n"
    )

    return {
        "answer": answer,
        "sources": sources
    }