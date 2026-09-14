from ingestion.scanner import load_repository
from parser.chunker import chunk_documents
from rag.vector_store import insert_chunks


# ============================================================
# Integration Test
# Scanner → Chunker → Vector Store
# ============================================================

def test_repository_indexing_pipeline():

    repository_path = "data/monetrik-financesystem"

    # --------------------------------------------------------
    # Step 1: Load repository
    # --------------------------------------------------------

    documents = load_repository(
        repository_path
    )

    assert documents
    assert len(documents) > 0

    # --------------------------------------------------------
    # Step 2: Chunk documents
    # --------------------------------------------------------

    chunks = chunk_documents(
        documents,
        chunk_size=80,
        chunk_overlap=10
    )

    assert chunks
    assert len(chunks) > 0

    # --------------------------------------------------------
    # Step 3: Validate chunk structure
    # --------------------------------------------------------

    first_chunk = chunks[0]

    assert "content" in first_chunk
    assert "metadata" in first_chunk

    assert first_chunk["content"].strip()

    metadata = first_chunk["metadata"]

    assert metadata["filename"]
    assert metadata["relative_path"]
    assert metadata["language"]
    assert metadata["chunk_type"] == "text"

    # --------------------------------------------------------
    # Step 4: Insert into Qdrant
    # --------------------------------------------------------

    collection_name = insert_chunks(
        chunks,
        repository_path=repository_path
    )

    assert collection_name