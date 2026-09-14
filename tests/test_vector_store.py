from rag.vector_store import (
    normalize_repository_path,
    get_collection_name,
)


# ============================================================
# Test 1: Repository path normalization
# ============================================================

def test_normalize_repository_path():

    path = "data/monetrik-financesystem"

    normalized = normalize_repository_path(path)

    assert normalized
    assert normalized == normalize_repository_path(path)


# ============================================================
# Test 2: Collection name generation
# ============================================================

def test_get_collection_name():

    path = "data/monetrik-financesystem"

    collection_name = get_collection_name(path)

    assert collection_name == (
        "codebase_chunks_monetrik_financesystem"
    )


# ============================================================
# Test 3: Different repositories get different collections
# ============================================================

def test_different_repository_collection_names():

    repo1 = "data/project-one"
    repo2 = "data/project-two"

    collection1 = get_collection_name(repo1)
    collection2 = get_collection_name(repo2)

    assert collection1 != collection2


# ============================================================
# Test 4: Collection name is normalized
# ============================================================

def test_collection_name_normalization():

    path = "data/My-Test_Project"

    collection_name = get_collection_name(path)

    assert collection_name == (
        "codebase_chunks_my_test_project"
    )