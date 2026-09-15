import atexit
import logging
import os
import sys
import uuid
import warnings

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
from core.config import get_runtime_config


BASE_COLLECTION_NAME = "codebase_chunks"
QDRANT_PATH = "data/qdrant"

_client_instance = None
logger = logging.getLogger(__name__)


def get_client() -> QdrantClient:
    """
    Get or create the shared QdrantClient instance.
    """
    global _client_instance
    if _client_instance is None:
        qdrant_path = get_runtime_config()["qdrant_path"]
        os.makedirs(qdrant_path, exist_ok=True)
        _client_instance = QdrantClient(path=qdrant_path)
    return _client_instance


def close_client():
    """
    Safely close the Qdrant client before interpreter shutdown.
    """
    global _client_instance
    if _client_instance is not None:
        try:
            _client_instance.close()
        except Exception:
            pass
        finally:
            _client_instance = None


# Register defensive atexit cleanup to avoid Python 3.14 deallocator warnings
atexit.register(close_client)


class _ClientProxy:
    """
    Proxy to allow transparent access to the singleton client instance
    while keeping lifecycle management robust.
    """
    def __getattr__(self, name):
        return getattr(get_client(), name)


client = _ClientProxy()


def normalize_repository_path(repository_path: str) -> str:
    """
    Normalize repository paths so Windows path variations
    are treated consistently.
    """
    if not repository_path:
        return ""
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
    Create a separate Qdrant collection for the repository if it doesn't exist.
    """
    collection_name = get_collection_name(repository_path)
    qclient = get_client()

    if not qclient.collection_exists(collection_name):
        qclient.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=384,
                distance=Distance.COSINE
            )
        )

    return collection_name


def delete_repository_chunks(repository_path: str):
    """
    Delete all existing vectors belonging to the repository collection.
    """
    collection_name = get_collection_name(repository_path)
    qclient = get_client()

    if not qclient.collection_exists(collection_name):
        return

    qclient.delete(
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
    collection_name = get_collection_name(repository_path)
    qclient = get_client()

    points = []
    normalized_repository_path = normalize_repository_path(repository_path)

    for index, chunk in enumerate(chunks):
        metadata = chunk.get("metadata", {})
        content = chunk.get("content", "")

        if not content.strip():
            continue

        filename = metadata.get("filename", "")
        file_path = metadata.get("file_path", "")
        relative_path = metadata.get("relative_path", "")
        language = metadata.get("language", "")
        extension = metadata.get("extension", "")

        embedding_text = f"""
File: {filename}

Path: {relative_path}

Full Path: {file_path}

Language: {language}

Extension: {extension}

Code:
{content}
""".strip()

        vector = generate_embedding(embedding_text)

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

    if points:
        # Upsert deterministic IDs in place so failed batches preserve the
        # previously usable repository index.
        create_collection(repository_path)

        # Upsert in batches of 100
        batch_size = 100
        for i in range(0, len(points), batch_size):
            qclient.upsert(
                collection_name=collection_name,
                points=points[i:i + batch_size]
            )

    return collection_name


def collection_exists(
    repository_path: str
) -> bool:
    collection_name = get_collection_name(repository_path)
    return get_client().collection_exists(collection_name)


def list_repositories():
    """
    Return all repositories that have been indexed.
    """
    collections = (
        get_client().get_collections().collections
    )

    repositories = []
    prefix = BASE_COLLECTION_NAME + "_"

    for collection in collections:
        collection_name = collection.name
        if not collection_name.startswith(prefix):
            continue

        repository_name = collection_name[len(prefix):]
        repositories.append({
            "name": repository_name,
            "collection_name": collection_name
        })

    return repositories