import os
import sys

sys.path.append(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

from ingestion.scanner import load_repository
from parser.chunker import chunk_documents
from parser.tree_parser import parse_repository
from rag.vector_store import create_collection, insert_chunks


def index_repository(repository_path: str):
    """
    Load, chunk, parse and index an entire repository.

    Pipeline:

        Repository
            ↓
        Scanner
            ↓
        Documents
            ↓
        Code Chunks
            ↓
        Tree-sitter Parsed Items
            ↓
        Qdrant
    """

    # --------------------------------------------------
    # Validate repository path
    # --------------------------------------------------

    if not repository_path:
        raise ValueError(
            "repository_path is required"
        )

    repository_path = os.path.normpath(
        repository_path
    )

    if not os.path.exists(repository_path):
        raise FileNotFoundError(
            f"Repository does not exist: {repository_path}"
        )

    if not os.path.isdir(repository_path):
        raise ValueError(
            f"Repository path is not a directory: {repository_path}"
        )

    # --------------------------------------------------
    # Step 1: Load repository files
    # --------------------------------------------------

    documents = load_repository(
        repository_path
    )

    print(
        f"Total documents: {len(documents)}"
    )

    if not documents:
        raise ValueError(
            f"No supported files found in repository: "
            f"{repository_path}"
        )

    # --------------------------------------------------
    # Step 2: Create normal code chunks
    # --------------------------------------------------

    chunks = chunk_documents(
        documents
    )

    print(
        f"Total code chunks: {len(chunks)}"
    )

    # --------------------------------------------------
    # Step 3: Parse JavaScript / JSX structure
    # --------------------------------------------------

    parsed_items = parse_repository(
        repository_path
    )

    print(
        f"Total parsed items: {len(parsed_items)}"
    )

    # --------------------------------------------------
    # Step 4: Combine normal chunks + parsed items
    # --------------------------------------------------

    chunks.extend(
        parsed_items
    )

    print(
        f"Total chunks after parsing: {len(chunks)}"
    )

    if not chunks:
        raise ValueError(
            f"No indexable content found in repository: "
            f"{repository_path}"
        )

    # --------------------------------------------------
    # Step 5: Create repository-specific collection
    # --------------------------------------------------

    collection_name = create_collection(
        repository_path
    )

    print(
        f"Qdrant collection: {collection_name}"
    )

    # --------------------------------------------------
    # Step 6: Generate embeddings and store chunks
    # --------------------------------------------------

    insert_chunks(
        chunks,
        repository_path
    )

    print(
        f"Repository indexed successfully: "
        f"{repository_path}"
    )

    print(
        f"Collection: {collection_name}"
    )

    print(
        f"Indexed chunks: {len(chunks)}"
    )

    return collection_name