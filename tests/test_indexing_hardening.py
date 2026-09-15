import pytest

from parser.chunker import chunk_documents
from rag import vector_store


def test_malformed_documents_are_skipped_without_stopping_chunking():
    documents = [
        None,
        {"content": 123, "metadata": {}},
        {"content": "valid", "metadata": {"filename": "ok.py"}},
    ]

    chunks = chunk_documents(documents)

    assert len(chunks) == 1
    assert chunks[0]["content"] == "valid"


def test_invalid_chunk_configuration_does_not_stop_other_documents():
    documents = [
        {"content": "first", "metadata": {}},
        {"content": "second", "metadata": {}},
    ]

    with pytest.raises(ValueError):
        chunk_documents(documents, chunk_size=0)


class _FakeQdrantClient:
    def __init__(self):
        self.delete_calls = 0
        self.upserted_ids = []

    def collection_exists(self, name):
        return True

    def delete_collection(self, name):
        self.delete_calls += 1

    def create_collection(self, **kwargs):
        return None

    def upsert(self, collection_name, points):
        self.upserted_ids.extend(point.id for point in points)


def _chunk():
    return [{
        "content": "print('ok')",
        "metadata": {
            "filename": "main.py",
            "file_path": "repo/main.py",
            "relative_path": "main.py",
            "language": "python",
            "extension": ".py",
            "chunk_index": 0,
            "start_line": 1,
            "end_line": 1,
        },
    }]


def test_repeated_insertion_replaces_vectors_without_duplicate_ids(monkeypatch):
    client = _FakeQdrantClient()
    monkeypatch.setattr(vector_store, "get_client", lambda: client)
    monkeypatch.setattr(vector_store, "generate_embedding", lambda text: [0.1, 0.2])

    vector_store.insert_chunks(_chunk(), "repo")
    first_ids = list(client.upserted_ids)
    vector_store.insert_chunks(_chunk(), "repo")

    assert client.delete_calls == 2
    assert client.upserted_ids == first_ids + first_ids


def test_embedding_failure_does_not_delete_existing_collection(monkeypatch):
    client = _FakeQdrantClient()
    monkeypatch.setattr(vector_store, "get_client", lambda: client)

    def fail_embedding(text):
        raise RuntimeError("embedding unavailable")

    monkeypatch.setattr(vector_store, "generate_embedding", fail_embedding)

    with pytest.raises(RuntimeError, match="embedding unavailable"):
        vector_store.insert_chunks(_chunk(), "repo")

    assert client.delete_calls == 0