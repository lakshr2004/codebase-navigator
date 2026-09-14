import os
import sys

sys.path.append(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

from ingestion.scanner import (
    scan_repository,
    read_file,
    get_file_metadata,
)


# ============================================================
# Chunk Configuration
# ============================================================

DEFAULT_CHUNK_SIZE = 80
DEFAULT_CHUNK_OVERLAP = 10


# ============================================================
# Text Chunking
# ============================================================

def chunk_text(
    content: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[dict]:
    """
    Split source code into line-based chunks.

    Guarantees:
    - 0-line content -> []
    - 1..chunk_size lines -> exactly 1 chunk covering all lines
    - > chunk_size lines -> overlapped chunks covering every line through the end
    - exact 1-indexed start_line and end_line
    """
    if not content or not content.strip():
        return []

    if chunk_size <= 0:
        raise ValueError(
            "chunk_size must be greater than 0"
        )

    if chunk_overlap < 0:
        raise ValueError(
            "chunk_overlap cannot be negative"
        )

    if chunk_overlap >= chunk_size:
        raise ValueError(
            "chunk_overlap must be smaller than chunk_size"
        )

    lines = content.splitlines()
    total_lines = len(lines)

    if total_lines == 0:
        return []

    if total_lines <= chunk_size:
        return [{
            "content": content,
            "start_line": 1,
            "end_line": total_lines,
            "chunk_index": 0,
        }]

    chunks = []
    start = 0
    chunk_index = 0
    step = chunk_size - chunk_overlap

    while start < total_lines:
        end = min(start + chunk_size, total_lines)
        chunk_content = "\n".join(lines[start:end])

        if chunk_content.strip():
            chunks.append({
                "content": chunk_content,
                "start_line": start + 1,
                "end_line": end,
                "chunk_index": chunk_index,
            })
            chunk_index += 1

        if end >= total_lines:
            break

        start += step

    return chunks


# ============================================================
# Document Chunker
# ============================================================

def chunk_documents(
    documents: list[dict],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[dict]:
    """
    Convert loaded repository documents into standardized code chunks.
    """
    chunks = []

    for document in documents:
        content = document.get("content", "")
        metadata = document.get("metadata", {})

        file_chunks = chunk_text(
            content,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        for chunk in file_chunks:
            chunk_metadata = {
                **metadata,
                "chunk_type": "text",
                "chunk_index": chunk["chunk_index"],
                "start_line": chunk["start_line"],
                "end_line": chunk["end_line"],
            }

            chunks.append({
                "content": chunk["content"],
                "metadata": chunk_metadata,
            })

    return chunks


# ============================================================
# Repository Chunker
# ============================================================

def chunk_repository(
    repository_path: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[dict]:
    """
    Scan a repository and convert supported source files into standardized code chunks.
    """
    repository_path = os.path.abspath(
        os.path.normpath(repository_path)
    )

    files = scan_repository(repository_path)
    documents = []

    for file_path in files:
        try:
            content = read_file(file_path)
        except ValueError as e:
            print(f"Skipping file: {e}")
            continue

        metadata = get_file_metadata(
            file_path,
            repository_path
        )

        documents.append({
            "content": content,
            "metadata": metadata
        })

    return chunk_documents(
        documents,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )