import os
import sys
import logging

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


logger = logging.getLogger(__name__)


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

    logger.info("Repository documents discovered: %s", len(documents))

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

    logger.info("Repository text chunks created: %s", len(chunks))

    # --------------------------------------------------
    # Step 3: Parse JavaScript / JSX structure
    # --------------------------------------------------

    parsed_items = parse_repository(
        repository_path
    )

    logger.info("Repository parsed items created: %s", len(parsed_items))

    # --------------------------------------------------
    # Step 4: Combine normal chunks + parsed items
    # --------------------------------------------------

    chunks.extend(
        parsed_items
    )

    logger.info("Repository chunks after parsing: %s", len(chunks))

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

    logger.info("Qdrant collection selected: %s", collection_name)

    # --------------------------------------------------
    # Step 6: Generate embeddings and store chunks
    # --------------------------------------------------

    insert_chunks(
        chunks,
        repository_path
    )

    logger.info("Repository indexed successfully: %s", repository_path)
    logger.info("Indexed chunks: %s", len(chunks))

    return collection_name