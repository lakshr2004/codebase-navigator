from parser.chunker import chunk_text, chunk_documents


# ============================================================
# Test 1: Basic chunking
# ============================================================

def test_chunk_text_basic():
    content = "\n".join(
        f"line {i}"
        for i in range(1, 11)
    )

    chunks = chunk_text(
        content,
        chunk_size=4,
        chunk_overlap=1
    )

    assert len(chunks) == 3

    assert chunks[0]["start_line"] == 1
    assert chunks[0]["end_line"] == 4

    assert chunks[1]["start_line"] == 4
    assert chunks[1]["end_line"] == 7

    assert chunks[2]["start_line"] == 7
    assert chunks[2]["end_line"] == 10


# ============================================================
# Test 2: Empty content
# ============================================================

def test_chunk_text_empty():
    chunks = chunk_text("")

    assert chunks == []


# ============================================================
# Test 3: Invalid chunk size
# ============================================================

def test_invalid_chunk_size():
    try:
        chunk_text(
            "hello",
            chunk_size=0
        )
        assert False
    except ValueError:
        assert True


# ============================================================
# Test 4: Invalid overlap
# ============================================================

def test_invalid_overlap():
    try:
        chunk_text(
            "hello",
            chunk_size=10,
            chunk_overlap=10
        )
        assert False
    except ValueError:
        assert True


# ============================================================
# Test 5: Documents → chunks
# ============================================================

def test_chunk_documents():

    documents = [
        {
            "content": "line 1\nline 2\nline 3\nline 4\nline 5",
            "metadata": {
                "filename": "test.py",
                "relative_path": "src/test.py",
                "language": "python",
                "extension": ".py"
            }
        }
    ]

    chunks = chunk_documents(
        documents,
        chunk_size=3,
        chunk_overlap=1
    )

    assert len(chunks) == 2

    assert chunks[0]["content"] == (
        "line 1\nline 2\nline 3"
    )

    assert chunks[0]["metadata"]["filename"] == "test.py"
    assert chunks[0]["metadata"]["relative_path"] == "src/test.py"
    assert chunks[0]["metadata"]["language"] == "python"

    assert chunks[0]["metadata"]["chunk_type"] == "text"
    assert chunks[0]["metadata"]["chunk_index"] == 0

    assert chunks[0]["metadata"]["start_line"] == 1
    assert chunks[0]["metadata"]["end_line"] == 3

    assert chunks[1]["metadata"]["chunk_index"] == 1
    assert chunks[1]["metadata"]["start_line"] == 3
    assert chunks[1]["metadata"]["end_line"] == 5