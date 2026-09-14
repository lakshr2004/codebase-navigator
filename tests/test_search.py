from retrieval.search import (
    normalize_path,
    clean_source_path,
    get_file_language,
    is_repository_file_query,
    is_repository_structure_query,
    detect_language_filter,
    extract_filename_candidates,
    extract_query_tokens,
)


# ============================================================
# Test 1: Path normalization
# ============================================================

def test_normalize_path():

    path = r"data\project\src\app.py"

    normalized = normalize_path(path)

    assert normalized
    assert normalized == normalize_path(
        normalized
    )


# ============================================================
# Test 2: Clean source path
# ============================================================

def test_clean_source_path():

    repository = r"C:\projects\myrepo"

    file_path = r"C:\projects\myrepo\src\app.py"

    result = clean_source_path(
        file_path,
        repository
    )

    assert result == "src/app.py"


# ============================================================
# Test 3: File language detection
# ============================================================

def test_get_file_language():

    assert get_file_language("app.py") == "python"
    assert get_file_language("app.js") == "javascript"
    assert get_file_language("app.ts") == "typescript"
    assert get_file_language("index.html") == "html"
    assert get_file_language("style.css") == "css"
    assert get_file_language("data.json") == "json"


# ============================================================
# Test 4: Unknown file language
# ============================================================

def test_unknown_file_language():

    assert get_file_language("image.png") == "unknown"


# ============================================================
# Test 5: Repository file query detection
# ============================================================

def test_repository_file_query():

    assert is_repository_file_query(
        "What files are in the repository?"
    )

    assert is_repository_file_query(
        "List all files"
    )

    assert is_repository_file_query(
        "show project files"
    )

    assert not is_repository_file_query(
        "What does app.py do?"
    )


# ============================================================
# Test 6: Repository structure query detection
# ============================================================

def test_repository_structure_query():

    assert is_repository_structure_query(
        "What is the repository structure?"
    )

    assert is_repository_structure_query(
        "Show project structure"
    )

    assert is_repository_structure_query(
        "List all folders"
    )

    assert not is_repository_structure_query(
        "Where is app.py?"
    )


# ============================================================
# Test 7: Language filter detection
# ============================================================

def test_detect_language_filter():

    assert detect_language_filter(
        "What JavaScript files exist?"
    ) == "javascript"

    assert detect_language_filter(
        "List Python files"
    ) == "python"

    assert detect_language_filter(
        "Show HTML files"
    ) == "html"

    assert detect_language_filter(
        "What CSS files are present?"
    ) == "css"


# ============================================================
# Test 8: No language filter
# ============================================================

def test_no_language_filter():

    assert detect_language_filter(
        "What does the authentication code do?"
    ) is None


# ============================================================
# Test 9: Filename extraction
# ============================================================

def test_extract_filename_candidates():

    query = (
        "Where is srcipt.js and index.html?"
    )

    candidates = extract_filename_candidates(
        query
    )

    assert "srcipt.js" in candidates
    assert "index.html" in candidates


# ============================================================
# Test 10: Filename extraction without duplicates
# ============================================================

def test_filename_candidates_no_duplicates():

    query = (
        "Where is app.py? I need app.py"
    )

    candidates = extract_filename_candidates(
        query
    )

    assert candidates.count("app.py") == 1


# ============================================================
# Test 11: Query token extraction
# ============================================================

def test_extract_query_tokens():

    query = (
        "Where is increaseScore defined?"
    )

    tokens = extract_query_tokens(
        query
    )

    assert "increasescore" in tokens
    assert "where" not in tokens
    assert "is" not in tokens


# ============================================================
# Test 12: Identifier preservation
# ============================================================

def test_identifier_preservation():

    query = (
        "Find getNewHit and #pannel-bottom"
    )

    tokens = extract_query_tokens(
        query
    )

    assert "getnewhit" in tokens
    assert "#pannel-bottom" in tokens