import os
import sys

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

from ingestion.scanner import load_repository
from parser.chunker import chunk_documents
from rag.vector_store import create_collection, insert_chunks


def index_repository(repository_path: str):

    documents = load_repository(repository_path)

    print(f"Total documents: {len(documents)}")

    chunks = chunk_documents(documents)

    print(f"Total chunks: {len(chunks)}")

    collection_name = create_collection(repository_path)

    insert_chunks(
        chunks,
        repository_path
    )

    print(
        f"Repository indexed successfully: {collection_name}"
    )

    return collection_name