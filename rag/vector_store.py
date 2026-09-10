import os
import sys

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

from parser.chunker import chunk_documents
from ingestion.scanner import load_repository
from rag.embeddings import generate_embedding


COLLECTION_NAME = "codebase_chunks"

client = QdrantClient(path="data/qdrant")


def create_collection():
    if not client.collection_exists(COLLECTION_NAME):
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=384,
                distance=Distance.COSINE
            )
        )


def insert_chunks(chunks):
    points = []

    for index, chunk in enumerate(chunks):
        vector = generate_embedding(chunk["content"])

        points.append(
            PointStruct(
                id=index,
                vector=vector,
                payload={
                    "content": chunk["content"],
                    "metadata": chunk["metadata"]
                }
            )
        )

    client.upsert(
        collection_name=COLLECTION_NAME,
        points=points
    )


if __name__ == "__main__":
    repository_path = "data/monetrik-financesystem"

    documents = load_repository(repository_path)
    chunks = chunk_documents(documents)

    print(f"Total documents: {len(documents)}")
    print(f"Total chunks: {len(chunks)}")

    create_collection()

    insert_chunks(chunks)

    collection_info = client.get_collection(COLLECTION_NAME)

    print("Vectors inserted successfully")
    print("Stored vectors:", collection_info.points_count)