import os
import tempfile
from unittest.mock import patch

from ingestion.scanner import (
    get_repository_files,
    get_repository_folders,
    get_file_language,
    is_binary_file,
    is_supported_file,
    normalize_path,
    get_relative_path,
    scan_repository,
)

from parser.chunker import chunk_text, chunk_documents
from retrieval.search import (
    search_repository_identifier,
    is_identifier_query,
    extract_identifier_candidates,
    detect_language_filter,
    classify_identifier_match_type,
    answer_query,
)


# ============================================================
# Test Suite A: Chunking Coverage & Line Preservation
# ============================================================

def test_chunking_empty_file():
    assert chunk_text("") == []
    assert chunk_text("   \n\n  ") == []


def test_chunking_1_line_file():
    chunks = chunk_text("console.log('hello');", chunk_size=80)
    assert len(chunks) == 1
    assert chunks[0]["start_line"] == 1
    assert chunks[0]["end_line"] == 1
    assert chunks[0]["content"] == "console.log('hello');"


def test_chunking_10_line_file():
    content = "\n".join([f"line_{i}" for i in range(1, 11)])
    chunks = chunk_text(content, chunk_size=80)
    assert len(chunks) == 1
    assert chunks[0]["start_line"] == 1
    assert chunks[0]["end_line"] == 10


def test_chunking_79_line_file():
    content = "\n".join([f"line_{i}" for i in range(1, 80)])
    chunks = chunk_text(content, chunk_size=80)
    assert len(chunks) == 1
    assert chunks[0]["start_line"] == 1
    assert chunks[0]["end_line"] == 79


def test_chunking_80_line_file():
    content = "\n".join([f"line_{i}" for i in range(1, 81)])
    chunks = chunk_text(content, chunk_size=80)
    assert len(chunks) == 1
    assert chunks[0]["start_line"] == 1
    assert chunks[0]["end_line"] == 80


def test_chunking_81_line_file():
    content = "\n".join([f"line_{i}" for i in range(1, 82)])
    chunks = chunk_text(content, chunk_size=80, chunk_overlap=10)
    assert len(chunks) == 2
    assert chunks[0]["start_line"] == 1
    assert chunks[0]["end_line"] == 80
    assert chunks[1]["start_line"] == 71
    assert chunks[1]["end_line"] == 81


def test_chunking_large_file_no_skipped_lines():
    total = 200
    content = "\n".join([f"line_{i}" for i in range(1, total + 1)])
    chunks = chunk_text(content, chunk_size=80, chunk_overlap=10)
    assert len(chunks) > 2

    # Verify final chunk reaches the very last line
    assert chunks[-1]["end_line"] == total

    # Verify continuous coverage
    for i in range(len(chunks) - 1):
        assert chunks[i + 1]["start_line"] <= chunks[i]["end_line"]


# ============================================================
# Test Suite B: Identifier Matching & Substring Protection
# ============================================================

def test_identifier_substring_protection():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "test.js")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(
                "const getRecords = () => {};\n"
                "const getRecordsBackup = () => {};\n"
                "const mygetRecords = () => {};\n"
                "const getRecords2 = () => {};\n"
                "const _getRecords = () => {};\n"
                "const getRecords_extra = () => {};\n"
                "getRecords();\n"
            )

        matches = search_repository_identifier("getRecords", tmpdir)

        # Should match line 1 and line 7, but NOT lines 2, 3, 4, 5, 6
        matched_lines = [m["start_line"] for m in matches]
        assert 1 in matched_lines
        assert 7 in matched_lines
        assert 2 not in matched_lines
        assert 3 not in matched_lines
        assert 4 not in matched_lines
        assert 5 not in matched_lines
        assert 6 not in matched_lines


def test_identifier_css_selector():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "style.css")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(
                "#pannel-bottom { color: red; }\n"
                "#pannel-bottom-inner { color: blue; }\n"
            )

        matches = search_repository_identifier("#pannel-bottom", tmpdir)
        matched_lines = [m["start_line"] for m in matches]
        assert 1 in matched_lines
        assert 2 not in matched_lines


def test_identifier_naming_varieties():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "types.ts")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(
                "export const camelCaseVar = 1;\n"
                "export class PascalCaseClass {}\n"
                "export const snake_case_var = 2;\n"
                "export const SCREAMING_SNAKE = 3;\n"
                "export const $jqueryObj = 4;\n"
            )

        assert len(search_repository_identifier("camelCaseVar", tmpdir)) == 1
        assert len(search_repository_identifier("PascalCaseClass", tmpdir)) == 1
        assert len(search_repository_identifier("snake_case_var", tmpdir)) == 1
        assert len(search_repository_identifier("SCREAMING_SNAKE", tmpdir)) == 1
        assert len(search_repository_identifier("$jqueryObj", tmpdir)) == 1


# ============================================================
# Test Suite C: Definition vs Reference / Import Classification
# ============================================================

def test_definition_vs_require_import_classification():
    # Require/import lines MUST be reference
    assert classify_identifier_match_type('const User = require("../models/User");', "User") == "reference"
    assert classify_identifier_match_type('const { User } = require("./models/User");', "User") == "reference"
    assert classify_identifier_match_type('import User from "../models/User";', "User") == "reference"
    assert classify_identifier_match_type('import { User } from "../models/User";', "User") == "reference"
    assert classify_identifier_match_type('from models import User', "User") == "reference"

    # Actual Model / Class / Function definitions
    assert classify_identifier_match_type('module.exports = mongoose.model("User", userSchema);', "User") == "definition"
    assert classify_identifier_match_type('export default class User {}', "User") == "definition"
    assert classify_identifier_match_type('class User extends Model {}', "User") == "definition"
    assert classify_identifier_match_type('const loginUser = async (req, res) => {', "loginUser") == "definition"
    assert classify_identifier_match_type('export const logout = async () => {', "logout") == "definition"

    # Usages
    assert classify_identifier_match_type('const user = await User.findById(id);', "User") == "usage"
    assert classify_identifier_match_type('onClick={logout}', "logout") == "usage"


def test_definition_classification_in_file():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "calc.js")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(
                "import { calculateBalance } from './api';\n"
                "export const calculateBalance = (a, b) => a - b;\n"
                "const result = calculateBalance(100, 50);\n"
            )

        matches = search_repository_identifier("calculateBalance", tmpdir)
        types_by_line = {m["start_line"]: m["type"] for m in matches}

        assert types_by_line[1] == "reference"
        assert types_by_line[2] == "definition"
        assert types_by_line[3] == "usage"


# ============================================================
# Test Suite D: Negative Identifier (No Hallucination & No RAG)
# ============================================================

def test_negative_identifier_never_calls_rag():
    repo_path = "data/monetrik-financesystem"
    assert os.path.isdir(repo_path)

    # Missing identifier: increaseScore
    with patch("retrieval.search.search_code") as mock_rag:
        result = answer_query("Where is increaseScore defined?", repo_path)

        # Assert deterministic negative answer returned
        assert "couldn't find the identifier `increaseScore`" in result["answer"]
        assert result["sources"] == []

        # Verify semantic RAG was never invoked
        mock_rag.assert_not_called()


def test_nonexistent_identifier_xyz():
    repo_path = "data/monetrik-financesystem"
    result = answer_query("Where is xyzDefinitelyDoesNotExist123 defined?", repo_path)
    assert "couldn't find the identifier `xyzDefinitelyDoesNotExist123`" in result["answer"]
    assert result["sources"] == []


# ============================================================
# Test Suite E: Filename Location & Missing Filename
# ============================================================

def test_filename_location_existing():
    repo_path = "data/monetrik-financesystem"
    result = answer_query("Where is Analysis.jsx?", repo_path)
    assert "Analysis.jsx" in result["answer"]
    assert len(result["sources"]) >= 1
    assert any("Analysis.jsx" in s["file"] for s in result["sources"])


def test_filename_location_index_html():
    repo_path = "data/monetrik-financesystem"
    result = answer_query("Where is index.html?", repo_path)
    assert "index.html" in result["answer"]
    assert any("index.html" in s["file"] for s in result["sources"])


def test_filename_location_nonexistent():
    repo_path = "data/monetrik-financesystem"
    result = answer_query("Where is NonExistentFile.jsx?", repo_path)
    assert "couldn't find a file named `NonExistentFile.jsx`" in result["answer"]
    assert result["sources"] == []


# ============================================================
# Test Suite F: Language Filter Detection
# ============================================================

def test_language_filters():
    assert detect_language_filter("What JavaScript files exist?") == "javascript"
    assert detect_language_filter("Which Python files are there?") == "python"
    assert detect_language_filter("Show HTML files") == "html"
    assert detect_language_filter("List all CSS files") == "css"
    assert detect_language_filter("What JSON files exist?") == "json"
    assert detect_language_filter("How does authentication work?") is None


# ============================================================
# Test Suite G: Path Normalization
# ============================================================

def test_path_normalization_forward_slashes():
    with tempfile.TemporaryDirectory() as tmpdir:
        nested_dir = os.path.join(tmpdir, "src", "nested")
        os.makedirs(nested_dir)
        file_path = os.path.join(nested_dir, "App.jsx")
        with open(file_path, "w") as f:
            f.write("export default function App() {}")

        files = get_repository_files(tmpdir)
        assert files == ["src/nested/App.jsx"]
        assert "\\" not in files[0]


# ============================================================
# Test Suite H: Scanner Ignored Directories and Supported Files
# ============================================================

def test_scanner_ignored_dirs_and_binaries():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create ignored dirs
        git_dir = os.path.join(tmpdir, ".git")
        node_dir = os.path.join(tmpdir, "node_modules")
        os.makedirs(git_dir)
        os.makedirs(node_dir)
        with open(os.path.join(git_dir, "config"), "w") as f:
            f.write("git config")
        with open(os.path.join(node_dir, "package.json"), "w") as f:
            f.write("{}")

        # Create valid source file and binary file
        src_dir = os.path.join(tmpdir, "src")
        os.makedirs(src_dir)
        with open(os.path.join(src_dir, "index.js"), "w") as f:
            f.write("console.log('hi');")
        with open(os.path.join(src_dir, "icon.png"), "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n\x00\x00")

        files = get_repository_files(tmpdir)
        assert files == ["src/index.js"]
        assert "icon.png" not in str(files)
        assert ".git" not in str(files)
        assert "node_modules" not in str(files)


# ============================================================
# Test Suite I: Hinglish Queries
# ============================================================

def test_hinglish_queries():
    assert is_identifier_query("loginUser kaha defined hai?") is True
    assert is_identifier_query("getRecords kaha use hua hai?") is True
    assert "loginUser" in extract_identifier_candidates("loginUser kaha defined hai?")
    assert "getRecords" in extract_identifier_candidates("getRecords kaha use hua hai?")


# ============================================================
# Test Suite J: Real Monetrik Integration
# ============================================================

def test_monetrik_user_model_definition():
    repo_path = "data/monetrik-financesystem"
    assert os.path.isdir(repo_path)

    user_result = answer_query("Where is User defined?", repo_path)
    assert "Found definition(s) for `User`" in user_result["answer"]
    # Must identify models/User.js as the actual definition
    assert any("models/User.js" in s["file"] for s in user_result["sources"])
    # Must NOT classify controllers/authController.js line 1 as definition
    assert not any("controllers/authController.js" in s["file"] for s in user_result["sources"])


def test_monetrik_real_identifiers():
    repo_path = "data/monetrik-financesystem"
    assert os.path.isdir(repo_path)

    # Positive definition search for loginUser
    login_result = answer_query("Where is loginUser defined?", repo_path)
    assert "Found definition(s) for `loginUser`" in login_result["answer"]
    assert any("authController.js" in s["file"] for s in login_result["sources"])

    # Hinglish definition search
    hinglish_result = answer_query("loginUser kaha defined hai?", repo_path)
    assert "Found definition(s) for `loginUser`" in hinglish_result["answer"]
    assert any("authController.js" in s["file"] for s in hinglish_result["sources"])

    # Positive usage search
    records_result = answer_query("Find all usages of getRecords", repo_path)
    assert "Found usages/references of `getRecords`" in records_result["answer"]
    assert len(records_result["sources"]) >= 3

    # Logout definitions
    logout_result = answer_query("Where is logout implemented?", repo_path)
    assert "Found definition(s) for `logout`" in logout_result["answer"]
    assert any("AuthContext.jsx" in s["file"] or "auth.js" in s["file"] for s in logout_result["sources"])

    # Language file listing
    js_result = answer_query("What JavaScript files exist?", repo_path)
    assert "javascript file(s)" in js_result["answer"].lower()
    assert len(js_result["sources"]) > 10
