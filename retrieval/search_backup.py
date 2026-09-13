import os
import sys

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

from rag.vector_store import (
    client,
    get_collection_name
)

from rag.embeddings import generate_embedding
from rag.generator import generate_answer


# Minimum similarity score required
SIMILARITY_THRESHOLD = 0.15


def normalize_path(file_path: str) -> str:
    """
    Normalize file paths so that Windows path variations
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
    Convert an absolute/full repository path into
    a clean repository-relative path.
    """

    normalized_file = normalize_path(file_path)
    normalized_repo = normalize_path(repository_path)

    if normalized_file.startswith(normalized_repo):
        relative_path = normalized_file[
            len(normalized_repo):
        ].lstrip("\\/")

        return relative_path.replace("\\", "/")

    return normalized_file.replace("\\", "/")


def deduplicate_results(results):
    """
    Remove duplicate chunks while keeping
    the highest-scoring result.

    A chunk is considered duplicate when:
    file path + line range are identical.
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

        normalized_path = normalize_path(
            file_path
        )

        key = (
            normalized_path,
            start_line,
            end_line
        )

        # Keep highest-scoring result
        if (
            key not in unique_results
            or result.score > unique_results[key].score
        ):
            unique_results[key] = result

    # Restore similarity ranking
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
    Prevent too many results from the same file
    from dominating the final retrieval context.

    Keeps the highest-scoring chunks first while
    limiting the number of chunks returned per file.
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

        selected_results.append(result)

        file_counts[normalized_path] = (
            current_count + 1
        )

    return selected_results


def search_code(
    query: str,
    repository_path: str,
    limit: int = 10
):
    """
    Search the indexed repository using
    semantic similarity.
    """

    collection_name = get_collection_name(
        repository_path
    )

    # Check if repository is indexed
    if not client.collection_exists(
        collection_name
    ):
        raise ValueError(
            f"Repository is not indexed: "
            f"{repository_path}"
        )

    # Convert user query into embedding
    query_vector = generate_embedding(
        query
    )

    # Retrieve more candidates than the final limit.
    # This gives deduplication and diversification
    # enough candidates to work with.
    retrieval_limit = max(
        limit * 3,
        20
    )

    # Search Qdrant
    results = client.query_points(
        collection_name=collection_name,
        query=query_vector,
        limit=retrieval_limit
    ).points

    # Remove low-quality matches
    relevant_results = [
        result
        for result in results
        if result.score >= SIMILARITY_THRESHOLD
    ]

    # Remove exact duplicate chunks
    unique_results = deduplicate_results(
        relevant_results
    )

    # Prevent one file from dominating retrieval
    diversified_results = diversify_results(
        unique_results,
        max_per_file=3
    )

    # Restore similarity ranking
    diversified_results = sorted(
        diversified_results,
        key=lambda result: result.score,
        reverse=True
    )

    return diversified_results[:limit]


def answer_query(
    query: str,
    repository_path: str,
    limit: int = 10
):
    """
    Retrieve relevant code and generate
    an AI answer.
    """

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

        # Convert full repository path
        # into clean relative source path
        file_path = clean_source_path(
            file_path,
            repository_path
        )

        # Build context for LLM
        context_parts.append(
            f"""
File: {file_path}

Language: {language}

Lines: {start_line} - {end_line}

Code:

{content}
"""
        )

        # Build source information
        sources.append({
            "file": file_path,
            "language": language,
            "start_line": start_line,
            "end_line": end_line,
            "score": result.score
        })

    # Combine retrieved chunks
    context = "\n".join(
        context_parts
    )

    # Generate final answer
    answer = generate_answer(
        query,
        context
    )

    return {
        "answer": answer,
        "sources": sources
    }