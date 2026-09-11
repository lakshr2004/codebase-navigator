import os
import sys
import uuid

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)

from rag.embeddings import generate_embedding


BASE_COLLECTION_NAME = "codebase_chunks"

client = QdrantClient(path="data/qdrant")


def get_collection_name(repository_path: str) -> str:
    """
    Generate a unique Qdrant collection name for each repository.
    """

    repository_name = os.path.basename(
        os.path.normpath(repository_path)
    )

    safe_name = "".join(
        character.lower() if character.isalnum() else "_"
        for character in repository_name
    )

    return f"{BASE_COLLECTION_NAME}_{safe_name}"


def create_collection(repository_path: str):
    """
    Create a separate Qdrant collection for the repository.
    """

    collection_name = get_collection_name(repository_path)

    if not client.collection_exists(collection_name):

        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=384,
                distance=Distance.COSINE
            )
        )

    return collection_name


def delete_repository_chunks(repository_path: str):
    """
    Delete all existing vectors belonging to the repository.
    """

    collection_name = get_collection_name(repository_path)

    if not client.collection_exists(collection_name):
        return

    client.delete(
        collection_name=collection_name,
        points_selector=Filter(
            must=[
                FieldCondition(
                    key="repository_path",
                    match=MatchValue(
                        value=repository_path
                    )
                )
            ]
        )
    )


def insert_chunks(
    chunks,
    repository_path: str
):
    """
    Generate embeddings and insert repository chunks
    into its dedicated Qdrant collection.
    """

    collection_name = create_collection(
        repository_path
    )

    # Remove old chunks before inserting fresh ones
    delete_repository_chunks(
        repository_path
    )

    points = []

    for index, chunk in enumerate(chunks):

        vector = generate_embedding(
            chunk["content"]
        )

        # Deterministic unique ID
        chunk_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"{repository_path}:{index}"
            )
        )

        points.append(
            PointStruct(
                id=chunk_id,
                vector=vector,
                payload={
                    "content": chunk["content"],
                    "metadata": chunk["metadata"],
                    "repository_path": repository_path
                }
            )
        )

    if points:

        client.upsert(
            collection_name=collection_name,
            points=points
        )

    return collection_name

def collection_exists(repository_path: str) -> bool:
    collection_name = get_collection_name(repository_path)

    return client.collection_exists(collection_name)


def list_repositories():
    """
    Return all repositories that have been indexed.
    """

    collections = client.get_collections().collections

    repositories = []

    for collection in collections:
        collection_name = collection.name

        if collection_name.startswith(BASE_COLLECTION_NAME + "_"):
            repository_name = collection_name[
                len(BASE_COLLECTION_NAME) + 1:
            ]

            repositories.append({
                "name": repository_name,
                "collection_name": collection_name
            })

    return repositories

if __name__ == "__main__":
    repository_path = "data/monetrik-financesystem"

    collection_name = create_collection(repository_path)

    print("Collection:", collection_name)
    print("Exists:", collection_exists(repository_path))
    print("Repositories:", list_repositories())