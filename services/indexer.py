import os
import sys

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

from ingestion.scanner import load_repository
from parser.chunker import chunk_documents
from parser.tree_parser import parse_repository
from rag.vector_store import create_collection, insert_chunks


def index_repository(repository_path: str):
    # Step 1: Load normal source files
    documents = load_repository(repository_path)
    print(f"Total documents: {len(documents)}")

    # Step 2: Create normal code chunks
    chunks = chunk_documents(documents)
    print(f"Total code chunks: {len(chunks)}")

    # Step 3: Parse JavaScript/JSX structure
    parsed_items = parse_repository(repository_path)
    print(f"Total parsed items: {len(parsed_items)}")

    # Step 4: Add parsed items to chunks
    chunks.extend(parsed_items)

    print(f"Total chunks after parsing: {len(chunks)}")

    # Step 5: Create Qdrant collection
    collection_name = create_collection(repository_path)

    # Step 6: Generate embeddings and store everything
    insert_chunks(
        chunks,
        repository_path
    )

    print(
        f"Repository indexed successfully: {collection_name}"
    )

    return collection_name