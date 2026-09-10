import os
import sys

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

from ingestion.scanner import load_repository
from parser.chunker import chunk_documents
from rag.vector_store import create_collection, insert_chunks


def index_repository(repository_path):

    documents = load_repository(repository_path)

    print(f"Total documents: {len(documents)}")

    chunks = chunk_documents(documents)

    print(f"Total chunks: {len(chunks)}")

    create_collection()

    insert_chunks(chunks)

    print("Repository indexed successfully")