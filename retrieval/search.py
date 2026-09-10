import os
import sys

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

from rag.vector_store import client, COLLECTION_NAME
from rag.embeddings import generate_embedding
from rag.generator import generate_answer


def search_code(query: str, limit: int = 5):
    query_vector = generate_embedding(query)

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        limit=limit,
    ).points

    return results


def answer_query(query: str, limit: int = 5):
    results = search_code(query, limit)

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

    answer = generate_answer(query, context)

    return {
        "answer": answer,
        "sources": sources
    }


if __name__ == "__main__":

    query = "Where is authentication handled?"

    result = answer_query(query)

    print("\n--- Final Answer ---\n")
    print(result["answer"])

    print("\n--- Sources ---\n")

    for source in result["sources"]:
        print(source)