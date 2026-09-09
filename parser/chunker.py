import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ingestion.scanner import load_repository


def chunk_code(
    content: str,
    chunk_size: int = 40,
    overlap: int = 5
) -> list[dict]:

    lines = content.splitlines()

    chunks = []

    start = 0
    chunk_index = 0

    while start < len(lines):

        end = min(start + chunk_size, len(lines))

        chunk_content = "\n".join(lines[start:end])

        if chunk_content.strip():
            chunks.append({
                "content": chunk_content,
                "chunk_index": chunk_index,
                "start_line": start + 1,
                "end_line": end
            })

            chunk_index += 1

        if end == len(lines):
            break

        start = end - overlap

    return chunks
    
def chunk_documents(documents: list[dict]) -> list[dict]:

    chunks = []

    for document in documents:

        content = document["content"]
        metadata = document["metadata"]

        code_chunks = chunk_code(content)

        for chunk in code_chunks:

            chunk_data = {
                "content": chunk["content"],
                "metadata": {
                    **metadata,
                    "chunk_index": chunk["chunk_index"],
                    "start_line": chunk["start_line"],
                    "end_line": chunk["end_line"]
                }
            }

            chunks.append(chunk_data)

    return chunks


if __name__ == "__main__":

    repository_path = "data/monetrik-financesystem"

    documents = load_repository(repository_path)

    chunks = chunk_documents(documents)

    print(f"Total documents: {len(documents)}")
    print(f"Total chunks: {len(chunks)}")

    print("\n--- First Chunk ---\n")

    print(chunks[0])