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
SIMILARITY_THRESHOLD = 0.20


def search_code(
    query: str,
    repository_path: str,
    limit: int = 5
):
    """
    Search the indexed repository using semantic similarity.
    """

    collection_name = get_collection_name(repository_path)

    # Check if repository is indexed
    if not client.collection_exists(collection_name):
        raise ValueError(
            f"Repository is not indexed: {repository_path}"
        )

    # Convert user query into embedding
    query_vector = generate_embedding(query)

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

    return relevant_results


def answer_query(
    query: str,
    repository_path: str,
    limit: int = 5
):
    """
    Retrieve relevant code and generate an AI answer.
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

    for result in results:

        payload = result.payload

        if not payload:
            continue

        metadata = payload.get("metadata", {})
        content = payload.get("content", "")

        file_path = metadata.get(
            "file_path",
            "Unknown file"
        )

        language = metadata.get(
            "language",
            "unknown"
        )

        start_line = metadata.get("start_line")
        end_line = metadata.get("end_line")

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
    context = "\n".join(context_parts)

    # Generate final answer
    answer = generate_answer(
        query,
        context
    )

    return {
        "answer": answer,
        "sources": sources
    }