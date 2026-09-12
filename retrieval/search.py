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


def deduplicate_results(results):
    """
    Remove duplicate chunks while keeping
    the highest-scoring result.

    A chunk is considered duplicate when
    file path + line range are identical.
    """
    unique_results = {}

    for result in results:
        payload = result.payload or {}

        if not payload:
            continue

        metadata = payload.get("metadata", {})

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

        # Same file + same line range = same chunk
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


def search_code(
    query: str,
    repository_path: str,
    limit: int = 10
):
    """
    Search the indexed repository using semantic similarity.
    """

    collection_name = get_collection_name(
        repository_path
    )

    # Check if repository is indexed
    if not client.collection_exists(
        collection_name
    ):
        raise ValueError(
            f"Repository is not indexed: {repository_path}"
        )

    # Convert user query into embedding
    query_vector = generate_embedding(
        query
    )

    # Search Qdrant
    results = client.query_points(
        collection_name=collection_name,
        query=query_vector,
        limit=limit
    ).points

    # Remove low-quality matches
    relevant_results = [
        result
        for result in results
        if result.score >= SIMILARITY_THRESHOLD
    ]

    # Remove duplicate chunks
    unique_results = deduplicate_results(
        relevant_results
    )

    # Return only requested number of results
    return unique_results[:limit]


def answer_query(
    query: str,
    repository_path: str,
    limit: int = 10
):
    """
    Retrieve relevant code and generate
    a grounded AI answer.
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
                "I couldn't find enough relevant information "
                "in the codebase."
            ),
            "sources": []
        }

    context_parts = []
    sources = []

    for index, result in enumerate(results, start=1):
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

        # Normalize path before returning it
        file_path = normalize_path(
            file_path
        )

        # Build clearly separated context
        context_parts.append(
            f"""
--- SOURCE {index} ---

File: {file_path}
Language: {language}
Lines: {start_line} - {end_line}
Similarity Score: {result.score:.4f}

Code:
{content}

--- END SOURCE {index} ---
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

    # Add grounding instructions around retrieved context
    grounded_context = f"""
You are answering a question about a software repository.

IMPORTANT:
- Answer using the retrieved repository context below.
- Do not invent files, functions, routes, classes, or behavior.
- If the retrieved context does not contain enough information,
  clearly say that the information is not available.
- Mention relevant file paths and line numbers when possible.
- Distinguish between frontend and backend code when relevant.

USER QUESTION:
{query}

RETRIEVED REPOSITORY CONTEXT:
{context}
"""

    # Generate final grounded answer
    answer = generate_answer(
        query,
        grounded_context
    )

    return {
        "answer": answer,
        "sources": sources
    }