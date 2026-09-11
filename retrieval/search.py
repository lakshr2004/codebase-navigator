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


# Minimum similarity score required for a result
SIMILARITY_THRESHOLD = 0.30


def search_code(
    query: str,
    repository_path: str,
    limit: int = 5
):
    collection_name = get_collection_name(repository_path)

    # Check whether repository has been indexed
    if not client.collection_exists(collection_name):
        raise ValueError(
            f"Repository is not indexed: {repository_path}"
        )

    query_vector = generate_embedding(query)

    results = client.query_points(
        collection_name=collection_name,
        query=query_vector,
        limit=limit,
    ).points

    # Remove weak / irrelevant matches
    results = [
        result
        for result in results
        if result.score >= SIMILARITY_THRESHOLD
    ]

    return results


def answer_query(
    query: str,
    repository_path: str,
    limit: int = 5
):
    results = search_code(
        query,
        repository_path,
        limit
    )

    # No sufficiently relevant code found
    if not results:
        return {
            "answer": "I couldn't find enough relevant information in the codebase.",
            "sources": []
        }

    context_parts = []
    sources = []

    for result in results:
        payload = result.payload

        metadata = payload["metadata"]
        content = payload["content"]

        context_parts.append(
            f"""
File: {metadata["file_path"]}

Language: {metadata["language"]}

Lines: {metadata.get("start_line")} - {metadata.get("end_line")}

Code:
{content}
"""
        )

        sources.append({
            "file": metadata["file_path"],
            "language": metadata["language"],
            "start_line": metadata.get("start_line"),
            "end_line": metadata.get("end_line"),
            "score": result.score,
        })

    context = "\n".join(context_parts)

    answer = generate_answer(
        query,
        context
    )

    return {
        "answer": answer,
        "sources": sources
    }