from parser.chunker import chunk_text, chunk_documents


def test_chunk_text():
    content = "\n".join(f"line {i}" for i in range(1, 201))

    chunks = chunk_text(
        content,
        chunk_size=80,
        chunk_overlap=10
    )

    assert len(chunks) > 1

    assert chunks[0]["start_line"] == 1
    assert chunks[0]["end_line"] == 80

    assert chunks[1]["start_line"] == 71
    assert chunks[1]["end_line"] == 150

    print("✅ chunk_text test passed")


def test_empty_content():
    chunks = chunk_text("")

    assert chunks == []

    print("✅ empty content test passed")


def test_invalid_chunk_size():
    try:
        chunk_text("hello", chunk_size=0)
        assert False
    except ValueError:
        pass

    print("✅ invalid chunk_size test passed")


def test_invalid_overlap():
    try:
        chunk_text(
            "hello",
            chunk_size=10,
            chunk_overlap=10
        )
        assert False
    except ValueError:
        pass

    print("✅ invalid overlap test passed")


def test_chunk_documents():
    documents = [
        {
            "content": "\n".join(
                f"line {i}" for i in range(1, 101)
            ),
            "metadata": {
                "filename": "test.py",
                "relative_path": "src/test.py",
                "language": "python",
                "extension": ".py"
            }
        }
    ]

    chunks = chunk_documents(documents)

    assert len(chunks) > 0

    first = chunks[0]

    assert "content" in first
    assert "metadata" in first

    metadata = first["metadata"]

    assert metadata["filename"] == "test.py"
    assert metadata["relative_path"] == "src/test.py"
    assert metadata["language"] == "python"
    assert metadata["extension"] == ".py"

    assert metadata["chunk_type"] == "text"
    assert metadata["chunk_index"] == 0
    assert metadata["start_line"] == 1
    assert metadata["end_line"] == 80

    print("✅ chunk_documents test passed")


if __name__ == "__main__":
    test_chunk_text()
    test_empty_content()
    test_invalid_chunk_size()
    test_invalid_overlap()
    test_chunk_documents()

    print("\n🎉 All chunker tests passed!")