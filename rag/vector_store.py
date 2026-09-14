import os
import sys
import uuid

sys.path.append(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
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

client = QdrantClient(
    path="data/qdrant"
)


def normalize_repository_path(repository_path: str) -> str:
    """
    Normalize repository paths so Windows path variations
    are treated consistently.
    """
    return os.path.normcase(
        os.path.normpath(
            os.path.abspath(repository_path)
        )
    )


def get_collection_name(repository_path: str) -> str:
    """
    Generate a unique Qdrant collection name for each repository.
    """

    repository_name = os.path.basename(
        os.path.normpath(repository_path)
    )

    safe_name = "".join(
        character.lower()
        if character.isalnum()
        else "_"
        for character in repository_name
    )

    return f"{BASE_COLLECTION_NAME}_{safe_name}"


def create_collection(repository_path: str):
    """
    Create a separate Qdrant collection for the repository.
    """

    collection_name = get_collection_name(
        repository_path
    )

    if not client.collection_exists(
        collection_name
    ):
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

    Since every repository has its own collection, deleting all
    points from that collection is sufficient for a clean re-index.
    """

    collection_name = get_collection_name(
        repository_path
    )

    if not client.collection_exists(
        collection_name
    ):
        return

    # Repository has a dedicated collection, so remove
    # all existing points before re-indexing.
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

    # Remove old vectors before inserting fresh data.
    delete_repository_chunks(
        repository_path
    )

    points = []

    normalized_repository_path = normalize_repository_path(
        repository_path
    )

    for index, chunk in enumerate(chunks):

        metadata = chunk.get(
            "metadata",
            {}
        )

        content = chunk.get(
            "content",
            ""
        )

        if not content.strip():
            continue

        # ------------------------------------------------
        # Standard metadata
        # ------------------------------------------------

        filename = metadata.get(
            "filename",
            ""
        )

        file_path = metadata.get(
            "file_path",
            ""
        )

        relative_path = metadata.get(
            "relative_path",
            ""
        )

        language = metadata.get(
            "language",
            ""
        )

        extension = metadata.get(
            "extension",
            ""
        )

        # ------------------------------------------------
        # Text used for embedding
        #
        # Include both metadata and source code so that
        # semantic search can understand file/path context.
        # ------------------------------------------------

        embedding_text = f"""
File: {filename}

Path: {relative_path}

Full Path: {file_path}

Language: {language}

Extension: {extension}

Code:
{content}
""".strip()

        vector = generate_embedding(
            embedding_text
        )

        # ------------------------------------------------
        # Deterministic unique ID
        # ------------------------------------------------

        chunk_identifier = (
            f"{normalized_repository_path}:"
            f"{relative_path}:"
            f"{metadata.get('chunk_index', index)}:"
            f"{metadata.get('start_line', '')}:"
            f"{metadata.get('end_line', '')}"
        )

        chunk_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL,
                chunk_identifier
            )
        )

        # ------------------------------------------------
        # Standardized payload
        # ------------------------------------------------

        payload_metadata = {
            **metadata,

            "filename": filename,
            "file_path": file_path,
            "relative_path": relative_path,
            "language": language,
            "extension": extension,
            "repository_path": repository_path,
        }

        points.append(
            PointStruct(
                id=chunk_id,
                vector=vector,
                payload={
                    "content": content,
                    "metadata": payload_metadata,
                    "repository_path": repository_path,
                }
            )
        )

    # ------------------------------------------------
    # Insert into Qdrant
    # ------------------------------------------------

    if points:
        client.upsert(
            collection_name=collection_name,
            points=points
        )

    return collection_name


def collection_exists(
    repository_path: str
) -> bool:

    collection_name = get_collection_name(
        repository_path
    )

    return client.collection_exists(
        collection_name
    )


def list_repositories():
    """
    Return all repositories that have been indexed.
    """

    collections = (
        client.get_collections().collections
    )

    repositories = []

    prefix = BASE_COLLECTION_NAME + "_"

    for collection in collections:

        collection_name = collection.name

        if not collection_name.startswith(
            prefix
        ):
            continue

        repository_name = collection_name[
            len(prefix):
        ]

        repositories.append({
            "name": repository_name,
            "collection_name": collection_name
        })

    return repositories


if __name__ == "__main__":

    repository_path = (
        "data/monetrik-financesystem"
    )

    collection_name = create_collection(
        repository_path
    )

    print(
        "Collection:",
        collection_name
    )

    print(
        "Exists:",
        collection_exists(
            repository_path
        )
    )

    print(
        "Repositories:",
        list_repositories()
    )