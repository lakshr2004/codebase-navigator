from pathlib import Path

from retrieval.search import (
    answer_query,
    build_exact_file_code_answer,
    search_repository_identifier,
)


# ------------------------------------------------------------
# Test repository
# ------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

REPOSITORY_PATH = PROJECT_ROOT / "data" / "repos" / "monetrik"


def get_answer(query: str) -> dict:
    """Run a query against the deterministic Monetrik test repository."""
    return answer_query(
        query=query,
        repository_path=str(REPOSITORY_PATH),
        mode="auto",
    )


# ------------------------------------------------------------
# T3-1
# Exact relevant code retrieval
# ------------------------------------------------------------

def test_exact_relevant_code_retrieval():
    result = get_answer(
        "Show the exact Record.js code that defines the user relationship."
    )

    answer = result["answer"]
    sources = result["sources"]

    assert "backend/models/Record.js" in answer

    assert "mongoose.Schema.Types.ObjectId" in answer
    assert 'ref: "User"' in answer
    assert "required: true" in answer

    assert len(sources) == 1

    source = sources[0]

    assert source["file"] == "backend/models/Record.js"
    assert source["start_line"] == 3
    assert source["end_line"] == 10
    assert source["score"] == 1.0


# ------------------------------------------------------------
# T3-2
# Exact complete file retrieval
# ------------------------------------------------------------

def test_exact_file_code_retrieval():
    result = get_answer("Show me Record.js")

    answer = result["answer"]
    sources = result["sources"]

    assert "Exact source code" in answer
    assert "backend/models/Record.js" in answer

    # Verify important parts of the actual file are returned.
    assert 'const mongoose = require("mongoose");' in answer
    assert "const recordSchema = new mongoose.Schema(" in answer
    assert 'mongoose.model("Record", recordSchema)' in answer

    assert len(sources) == 1

    source = sources[0]

    assert source["file"] == "backend/models/Record.js"
    assert source["start_line"] == 1
    assert source["end_line"] == 47
    assert source["score"] == 1.0


# ------------------------------------------------------------
# T3-3
# Missing file
# ------------------------------------------------------------

def test_missing_file_returns_deterministic_negative_answer():
    result = get_answer("Show the exact Payment.js code.")

    answer = result["answer"]

    assert "I couldn't find the requested file" in answer
    assert "Payment.js" in answer

    assert result["sources"] == []


# ------------------------------------------------------------
# T3-4
# Exact file location
# ------------------------------------------------------------

def test_exact_file_location():
    result = get_answer("Where is Record.js?")

    answer = result["answer"]
    sources = result["sources"]

    assert "backend/models/Record.js" in answer

    assert len(sources) == 1

    source = sources[0]

    assert source["file"] == "backend/models/Record.js"
    assert source["score"] == 1.0


# ------------------------------------------------------------
# T3-5
# Identifier definition + usage
# ------------------------------------------------------------

def test_identifier_usage_and_definition():
    result = get_answer("Where is recordSchema used?")

    answer = result["answer"]
    sources = result["sources"]

    assert "recordSchema" in answer

    # Definition
    assert "backend/models/Record.js" in answer
    assert "line 3" in answer

    # Usage
    assert "line 47" in answer

    assert len(sources) >= 2

    source_files = [source["file"] for source in sources]

    assert "backend/models/Record.js" in source_files


# ------------------------------------------------------------
# T3-6
# Identifier search for getRecords
# ------------------------------------------------------------

def test_get_records_identifier_search():
    result = get_answer("Where is getRecords used?")

    answer = result["answer"]
    sources = result["sources"]

    assert "getRecords" in answer

    # Backend definition
    assert "backend/controllers/recordController.js" in answer

    # Frontend definition
    assert "frontend/src/services/records.js" in answer

    # Frontend usage/reference
    assert "frontend/src/pages/Analysis.jsx" in answer
    assert "frontend/src/pages/Dashboard.jsx" in answer

    # Backend route usage
    assert "backend/routes/recordRoutes.js" in answer

    assert len(sources) >= 5


# ------------------------------------------------------------
# T3-7
# Missing identifier
# ------------------------------------------------------------

def test_missing_identifier_returns_deterministic_negative_answer():
    result = get_answer(
        "Where is completelyFakeFunctionXYZ used?"
    )

    answer = result["answer"]

    assert (
        "I couldn't find the identifier `completelyFakeFunctionXYZ`"
        in answer
    )

    assert result["sources"] == []


# ------------------------------------------------------------
# T3-8
# Token-boundary protection
# ------------------------------------------------------------

def test_identifier_boundary_protection():
    matches = search_repository_identifier(
        identifier="getRecords",
        repository_path=str(REPOSITORY_PATH),
    )

    assert matches

    for match in matches:
        content = match["content"]

        # The identifier itself should exist in the matched line.
        assert "getRecords" in content

        # A longer identifier such as getRecordsBackup should not
        # be treated as a match for getRecords.
        assert "getRecordsBackup" not in content


# ------------------------------------------------------------
# T3-9
# Direct exact-file retrieval
# ------------------------------------------------------------

def test_build_exact_file_code_answer_directly():
    result = build_exact_file_code_answer(
        query="Show me Record.js",
        repository_path=str(REPOSITORY_PATH),
    )

    assert result is not None

    assert "backend/models/Record.js" in result["answer"]
    assert 'const mongoose = require("mongoose");' in result["answer"]

    assert len(result["sources"]) == 1

    source = result["sources"][0]

    assert source["file"] == "backend/models/Record.js"
    assert source["start_line"] == 1
    assert source["end_line"] == 47


# ------------------------------------------------------------
# T3-10
# Direct relevant-block retrieval
# ------------------------------------------------------------

def test_build_exact_file_relevant_block_directly():
    result = build_exact_file_code_answer(
        query=(
            "Show the exact Record.js code "
            "that defines the user relationship."
        ),
        repository_path=str(REPOSITORY_PATH),
    )

    assert result is not None

    answer = result["answer"]

    assert "backend/models/Record.js" in answer

    assert "user: {" in answer
    assert "mongoose.Schema.Types.ObjectId" in answer
    assert 'ref: "User"' in answer

    # The targeted response should not return the entire 47-line file.
    source = result["sources"][0]

    assert source["start_line"] == 3
    assert source["end_line"] == 10