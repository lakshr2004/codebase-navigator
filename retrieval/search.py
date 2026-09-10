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

    # No relevant code found
    if not results:
        return {
            "answer": "No relevant code was found in this repository.",
            "sources": []
        }

    context_parts = []
    sources = []

    for result in results:
        metadata = result.payload["metadata"]
        content = result.payload["content"]

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