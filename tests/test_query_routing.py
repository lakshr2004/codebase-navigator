import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from retrieval.search import extract_identifier_candidates, is_code_like, is_identifier_query


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("Where is the main game logic defined?", False),
        ("Where is startGame defined?", True),
        ("Where is App defined?", True),
        ("Find all usages of main", True),
        ("Find all references to main", True),
        ("Where is the App component defined?", True),
        ("How does the game work?", False),
        ("Where is the game state managed?", False),
        ("How does collision detection work?", False),
        ("Where is handleSubmit defined?", True),
        ("Where is getUserById implemented?", True),
        ("loginUser kaha defined hai?", True),
        ("Where is the main component defined?", False),
    ],
)
def test_identifier_routing(query: str, expected: bool) -> None:
    assert is_identifier_query(query) is expected


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("startGame", True),
        ("handleSubmit", True),
        ("getUserById", True),
        ("App", True),
        ("AuthController", True),
        ("snake_case_identifier", True),
        ("foo_bar", True),
        ("$variable", True),
        ("`AuthController`", True),
        ("main", False),
        ("game", False),
        ("logic", False),
        ("state", False),
        ("authentication", False),
        ("collision", False),
    ],
)
def test_code_like_detection(token: str, expected: bool) -> None:
    assert is_code_like(token) is expected


def test_identifier_candidate_extraction_ignores_natural_language_phrases() -> None:
    assert extract_identifier_candidates("Where is the main game logic defined?") == []
    assert extract_identifier_candidates("Find all usages of main") == ["main"]
    assert extract_identifier_candidates("Where is handleSubmit defined?") == ["handleSubmit"]
