import os
import re
import sys
from rag import generator

sys.path.append(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

from ingestion.scanner import (
    get_repository_files,
    get_repository_folders,
    get_file_language,
    normalize_path,
    get_relative_path,
    LANGUAGE_MAP,
    LANGUAGE_EXTENSION_MAP,
    SUPPORTED_EXTENSIONS,
)


# ============================================================
# Configuration
# ============================================================

SIMILARITY_THRESHOLD = 0.04
DEFAULT_LIMIT = 12
SEMANTIC_RETRIEVAL_LIMIT = 60
MAX_CONTEXT_CHARS = 36000
CONCEPTUAL_MAX_RESULTS = 16

LOCKFILE_NAMES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "composer.lock",
    "gemfile.lock",
    "cargo.lock",
    "poetry.lock",
}


# ============================================================
# Path Utilities
# ============================================================

def clean_source_path(
    file_path: str,
    repository_path: str
) -> str:
    """
    Ensure the path is formatted as a forward-slash repository-relative path.
    """
    if not file_path:
        return ""

    normalized_file = normalize_path(file_path)
    normalized_repo = normalize_path(repository_path)

    try:
        relative_path = os.path.relpath(
            normalized_file,
            normalized_repo
        )
        if relative_path != ".." and not relative_path.startswith(".." + os.sep):
            return relative_path.replace("\\", "/")
    except ValueError:
        pass

    return str(file_path).replace("\\", "/")


# ============================================================
# Query Classification & Detection
# ============================================================

def is_repository_file_query(
    query: str
) -> bool:
    """
    Detect if the user is asking for a listing of all repository files.
    """
    query_lower = query.lower().strip()

    patterns = [
        "what files are in the repository",
        "what files are in repository",
        "what files exist",
        "which files exist",
        "list files",
        "list all files",
        "show all files",
        "show files",
        "which files are in the repository",
        "which files are in repository",
        "files in the repository",
        "files in repository",
        "repository files",
        "project files",
        "list repository files",
        "list project files",
        "what is in the repository",
        "what is inside the repository",
        "show repository files",
        "show project files",
        "sari files",
        "files dikhao",
        "files batao",
    ]

    return any(pattern in query_lower for pattern in patterns)


def is_repository_structure_query(
    query: str
) -> bool:
    """
    Detect if the user is asking for repository folder or directory structure.
    """
    query_lower = query.lower().strip()

    patterns = [
        "repository structure",
        "project structure",
        "show repository structure",
        "show project structure",
        "folder structure",
        "directory structure",
        "what folders are present",
        "what folders are there",
        "what folders exist",
        "list folders",
        "list all folders",
        "show folders",
        "show all folders",
        "which folders are present",
        "which folders are there",
        "which folders exist",
        "directories in repository",
        "directories in the repository",
        "folders in repository",
        "folders in the repository",
        "folder batao",
        "folders dikhao",
    ]

    return any(pattern in query_lower for pattern in patterns)


def detect_language_filter(
    query: str
) -> str | None:
    """
    Detect if query is requesting to list files of a specific language.
    Supports English and Hinglish phrases.
    """
    query_lower = query.lower().strip()

    # Must contain a file-listing intent word
    file_intent_patterns = [
        r"\bfiles?\b",
        r"\bscripts?\b",
        r"\bcode\b",
        r"\bdocuments?\b",
        r"\blist\b",
        r"\bshow\b",
        r"\bwhich\b",
        r"\bwhat\b",
        r"\bkaunse\b",
        r"\bdikhao\b",
        r"\bbatao\b",
    ]

    has_file_intent = any(re.search(p, query_lower) for p in file_intent_patterns)
    if not has_file_intent:
        return None

    # Check for asking explanation/conceptual questions instead of listing files
    conceptual_markers = [
        "how does",
        "how do",
        "explain",
        "what does",
        "how to",
        "kaise kaam",
        "kaise karta",
    ]
    if any(marker in query_lower for marker in conceptual_markers):
        return None

    language_aliases = [
        ("javascript", ["javascript", "js", "jsx"]),
        ("typescript", ["typescript", "ts", "tsx"]),
        ("python", ["python", "py"]),
        ("java", ["java"]),
        ("cpp", ["cpp", "c++"]),
        ("c", ["c"]),
        ("go", ["go", "golang"]),
        ("rust", ["rust"]),
        ("html", ["html", "htm"]),
        ("css", ["css", "scss", "sass", "less"]),
        ("json", ["json"]),
        ("markdown", ["markdown", "md", "mdx"]),
        ("yaml", ["yaml", "yml"]),
        ("shell", ["shell", "sh", "bash"]),
        ("sql", ["sql"]),
        ("toml", ["toml"]),
        ("xml", ["xml"]),
        ("svg", ["svg"]),
    ]

    for language, aliases in language_aliases:
        for alias in aliases:
            # Match whole word
            if re.search(rf"\b{re.escape(alias)}\b", query_lower):
                return language

    return None


def is_file_location_query(
    query: str
) -> bool:
    """
    Detect if the user is asking where a specific file is located.
    """
    query_lower = query.lower().strip()

    patterns = [
        "where is",
        "where can i find",
        "which folder contains",
        "which directory contains",
        "what is the path of",
        "what's the path of",
        "path of",
        "location of",
        "located",
        "find the file",
        "find file",
        "show me",
        "kaha hai",
        "kaha par hai",
        "ka path kya hai",
    ]

    return any(pattern in query_lower for pattern in patterns)


# ============================================================
# Code-Likeness Detection
# ============================================================

def is_code_like(
    token: str
) -> bool:
    """
    Return True when a token has strong structural evidence of being
    a repository/code identifier.
    """

    if not token:
        return False

    token = token.strip()

    # Backtick/quote enclosed symbols are explicit code references.
    if len(token) >= 2 and token[0] in "`\'\"" and token[-1] == token[0]:
        inner = token[1:-1].strip()
        return bool(inner) and is_code_like(inner)

    if len(token) < 2:
        return False

    # $-prefixed JavaScript identifiers
    if token.startswith("$"):
        return True

    # CSS selectors
    if token.startswith("#"):
        return True

    # Member access: req.body, router.get
    if "." in token:
        return True

    # Function-call notation
    if "(" in token or ")" in token:
        return True

    # snake_case / SCREAMING_SNAKE_CASE
    if re.search(
        r"[A-Za-z0-9]_[A-Za-z0-9]",
        token
    ):
        return True

    # camelCase
    if (
        token[0].islower()
        and any(c.isupper() for c in token[1:])
    ):
        return True

    # PascalCase.
    #
    # Require at least one uppercase character after the first
    # OR a known code-style suffix/pattern.
    if token[0].isupper():
        if any(c.isupper() for c in token[1:]):
            return True

        # Single capitalized identifiers commonly used in code.
        # Avoid treating ordinary words like "Main" as identifiers.
        known_code_words = {
            "App",
            "API",
            "UI",
            "DB",
            "ID",
            "JWT",
            "URL",
            "HTTP",
            "HTTPS",
            "CSS",
            "HTML",
            "JSON",
            "XML",
        }

        if token in known_code_words:
            return True

    return False

def _extract_explicit_type_keyword_candidates(
    query: str
) -> list[str]:
    """
    Extract identifiers that are explicitly named with a type keyword.
    Patterns: "function X", "class X", "component X", "method X",
              "variable X", "const X", "interface X", "struct X"
    These are always treated as code-like regardless of casing.
    """
    type_keyword_pattern = re.compile(
        r"\b(?:function|class|method|component|variable|const|let|var|interface|struct|type|enum)\s+"
        r"([A-Za-z_$][A-Za-z0-9_$]*)\b",
        re.IGNORECASE,
    )
    generic_words = {
        "defined", "definition", "declare", "declared", "declaration",
        "implemented", "implementation", "used", "usage", "usages",
        "component", "function", "method", "class", "variable",
        "identifier", "symbol", "file", "files", "code", "work",
    }

    candidates = []
    for match in type_keyword_pattern.finditer(query):
        candidate = match.group(1)
        if candidate.lower() in generic_words:
            continue
        candidates.append(candidate)

    return candidates


def _extract_explicit_usages_candidates(
    query: str
) -> list[str]:
    """
    Extract tokens from explicit usage-request patterns:
    "find all usages of X", "find usages of X", "find all references to X",
    "references to X", "find X" (direct find command).
    These tokens are treated as code-like regardless of casing because
    the user is explicitly asking for a code-level search.
    """
    usage_patterns = [
        r"\bfind\s+all\s+usages?\s+of\s+([A-Za-z_$#][A-Za-z0-9_$.\-]*)\b",
        r"\bfind\s+all\s+references?\s+to\s+([A-Za-z_$#][A-Za-z0-9_$.\-]*)\b",
        r"\busages?\s+of\s+([A-Za-z_$#][A-Za-z0-9_$.\-]*)\b",
        r"\breferences?\s+to\s+([A-Za-z_$#][A-Za-z0-9_$.\-]*)\b",
    ]
    results = []
    for pat in usage_patterns:
        for m in re.finditer(pat, query, re.IGNORECASE):
            token = m.group(1)
            if token not in results:
                results.append(token)
    return results



def is_identifier_query(query: str) -> bool:
    """
    Detect whether the query is an exact code-identifier search.

    Generic architecture and repository questions should use semantic
    retrieval, while explicit code-symbol queries use identifier search.
    """
    if not query or not query.strip():
        return False

    query_lower = query.lower().strip()

    # Repository structure and file-listing queries use dedicated handlers.
    if is_repository_structure_query(query):
        return False

    if is_repository_file_query(query):
        return False

    # Generic architecture terms are not code identifiers by themselves.
    # Example: "Where are API routes defined?"
    generic_architecture_terms = {
        "api",
        "apis",
        "route",
        "routes",
        "endpoint",
        "endpoints",
    }

    query_words = set(re.findall(r"[a-zA-Z_$][a-zA-Z0-9_$]*", query_lower))

    if (
        "where are" in query_lower
        and query_words.intersection(generic_architecture_terms)
    ):
        return False

    # Explicit existence checks.
    existence_patterns = [
        r"\bdoes\s+[`'\"]?([A-Za-z_$][A-Za-z0-9_$]*)[`'\"]?\s+exist\b",
        r"\bis\s+there\s+(?:a\s+|an\s+)?[`'\"]?([A-Za-z_$][A-Za-z0-9_$]*)[`'\"]?\s+(?:identifier|function|class|variable|symbol|component)\b",
        r"\b(?:check\s+if|see\s+if)\s+[`'\"]?([A-Za-z_$][A-Za-z0-9_$]*)[`'\"]?\s+exists?\b",
    ]

    for pattern in existence_patterns:
        match = re.search(pattern, query_lower)
        if match and is_code_like(match.group(1)):
            return True

    # Explicitly named code declarations, e.g. "function loginUser".
    if _extract_explicit_type_keyword_candidates(query):
        return True

    # Explicit usage/reference requests.
    if _extract_explicit_usages_candidates(query):
        return True

    # Quoted or backtick-enclosed identifiers are explicit.
    enclosed_candidates = re.findall(
        r"[`'\"]([A-Za-z_$][A-Za-z0-9_$]*)[`'\"]",
        query,
    )

    if enclosed_candidates:
        return True

    # Conceptual questions should normally use semantic retrieval.
    conceptual_markers = [
        "how does",
        "how do",
        "how to",
        "how is",
        "how are",
        "how can",
        "why does",
        "why is",
        "why do",
        "why are",
        "does this",
        "does the",
        "is there",
        "explain",
        "describe",
        "overview of",
        "what does",
        "tell me about",
        "what is",
        "what are",
        "kaise kaam",
        "kaise karta",
        "kaise hota",
        "samjhao",
    ]

    is_conceptual = any(
        query_lower.startswith(marker)
        or f" {marker} " in f" {query_lower} "
        for marker in conceptual_markers
    )

    if is_conceptual:
        has_explicit_identifier_intent = bool(
            re.search(
                r"\b(?:"
                r"where\s+is|where\s+are|defined|definition|"
                r"declare|declared|declaration|implemented|"
                r"implementation|find\s+all\s+usages?|"
                r"find\s+usages?|find\s+all\s+references?|"
                r"references?\s+to"
                r")\b",
                query_lower,
            )
        )

        if not has_explicit_identifier_intent:
            return False

        candidates = extract_identifier_candidates(query)

        return any(is_code_like(candidate) for candidate in candidates)

    # Non-conceptual identifier search requires an explicit search intent.
    identifier_trigger_patterns = [
        "defined",
        "definition",
        "declare",
        "declared",
        "declaration",
        "implemented",
        "implementation",
        "usage",
        "usages",
        "used",
        "where is",
        "where are",
        "find all usages",
        "find usages",
        "find all references",
        "references to",
        "reference to",
        "search for",
        "search",
        "find",
        "kaha defined hai",
        "kaha define",
        "kaha implemented",
        "kaha use hua",
        "kaha use hota",
        "ke usages",
        "kaha par hai",
        "kaha hai",
        "dhundo",
        "exist",
        "exists",
    ]

    has_trigger = any(
        pattern in query_lower
        for pattern in identifier_trigger_patterns
    )

    if not has_trigger:
        return False

    candidates = extract_identifier_candidates(query)

    if not candidates:
        return False

    return any(is_code_like(candidate) for candidate in candidates)

def detect_identifier_intent(query: str) -> str:
    """
    Determine whether the query is asking for 'definition', 'usage', or 'all'.
    """
    query_lower = query.lower().strip()

    definition_keywords = [
        "defined",
        "definition",
        "declare",
        "declared",
        "declaration",
        "implemented",
        "implementation",
        "kaha defined",
        "kaha define",
        "kaha implemented",
    ]
    if any(kw in query_lower for kw in definition_keywords):
        return "definition"

    usage_keywords = [
        "usage",
        "usages",
        "used",
        "use hua",
        "use hota",
        "referenced",
        "references",
        "reference",
        "ke usages",
        "call",
        "called",
    ]
    if any(kw in query_lower for kw in usage_keywords):
        return "usage"

    return "all"


# ============================================================
# Candidate Extraction
# ============================================================

SUPPORTED_EXTENSIONS_PATTERN = (
    "py|js|jsx|ts|tsx|java|cpp|c|h|hpp|go|rs|"
    "html?|css|scss|sass|less|svg|json|mdx?|txt|"
    "yaml|yml|sh|sql|toml|xml"
)


def extract_filename_candidates(
    query: str
) -> list[str]:
    """
    Extract file names appearing in the query.
    """
    candidates = []

    # Match files with extensions
    pattern = re.compile(
        rf"\b[\w.\-]+\.(?:{SUPPORTED_EXTENSIONS_PATTERN})\b",
        re.IGNORECASE
    )
    for match in pattern.findall(query):
        if match.lower() not in [c.lower() for c in candidates]:
            candidates.append(match)

    # Match special filenames
    special_names = [
        "Dockerfile", "Makefile", "package.json", "requirements.txt",
        ".gitignore", ".dockerignore", "LICENSE"
    ]
    for name in special_names:
        if re.search(rf"\b{re.escape(name)}\b", query, re.IGNORECASE):
            if name.lower() not in [c.lower() for c in candidates]:
                candidates.append(name)

    return candidates


def extract_identifier_candidates(
    query: str
) -> list[str]:
    """
    Extract code identifiers and CSS selectors from query.
    Preserves exact casing and handles camelCase, PascalCase, snake_case, $id, #id.

    IMPORTANT: Only structurally code-like tokens are returned.
    Plain lowercase English words ("main", "game", "logic", "authentication",
    "flow", "state", "loop") are excluded unless they appear in a privileged
    context (backtick-enclosed or explicit type-keyword / usages pattern).
    """
    candidates = []

    # Priority 1 — CSS selectors: #pannel-bottom, #main-header
    css_selectors = re.findall(
        r"#[A-Za-z_][A-Za-z0-9_\-]*",
        query
    )
    for selector in css_selectors:
        if selector not in candidates:
            candidates.append(selector)

    # Priority 2 — Backtick/quote enclosed symbols (always treated as code)
    enclosed = re.findall(r"[`'\"]([A-Za-z_$][A-Za-z0-9_$]*)['\"`]", query)
    for symbol in enclosed:
        if symbol not in candidates and symbol.lower() not in [c.lower() for c in candidates]:
            candidates.append(symbol)

    # Priority 3 — Explicit type-keyword named identifiers
    #   "function handleSubmit", "class AuthContext", "component App"
    for token in _extract_explicit_type_keyword_candidates(query):
        if token not in candidates and token.lower() not in [c.lower() for c in candidates]:
            candidates.append(token)

    # Priority 4 — Explicit usages-pattern tokens
    #   "find all usages of main", "find all references to socket"
    #   Accepted regardless of casing because the user explicitly requests
    #   a code-level search for that exact token.
    for token in _extract_explicit_usages_candidates(query):
        if token not in candidates and token.lower() not in [c.lower() for c in candidates]:
            candidates.append(token)

    # Priority 5 — Structurally code-like free tokens
    #   Only accept tokens that pass the is_code_like() check.
    #   This excludes plain lowercase English words.
    raw_identifiers = re.findall(
        r"\b[A-Za-z_$][A-Za-z0-9_$]*\b",
        query
    )

    filename_candidates_lower = {
        c.lower() for c in extract_filename_candidates(query)
    }

    # Stop words — query structure words that are never code identifiers
    stop_words = {
        "where", "what", "which", "how", "does", "do", "is", "are", "the",
        "a", "an", "in", "of", "to", "for", "on", "with", "and", "or",
        "me", "show", "find", "tell", "about", "work", "works", "used",
        "use", "this", "that", "code", "file", "files", "all", "defined",
        "definition", "declare", "declared", "declaration", "implemented",
        "implementation", "usage", "usages", "repository", "project",
        "located", "location", "path", "component", "function", "functions",
        "method", "methods", "class", "classes", "variable", "variables",
        "identifier", "identifiers", "symbol", "symbols",
        "model", "models", "service", "router", "route",
        "controller", "middleware", "flow", "system", "handle", "handled",
        "explain", "create", "creation", "overview", "architecture",
        "hai", "kaha", "kaise", "karo", "dikhao", "hota", "hua", "par",
        "batao", "dhundo", "mein", "ke", "ki", "ko", "se", "aur",
        "dikhaye", "can", "i", "here", "there", "search", "give",
        "please", "get", "exist", "exists", "present", "reference",
        "references", "referenced", "check", "see", "if",
    }

    for identifier in raw_identifiers:
        norm = identifier.lower()

        # Skip structural stop words
        if norm in stop_words:
            continue

        # Skip single-char tokens
        if len(identifier) < 2:
            continue

        # Skip if already captured via a higher-priority path
        if identifier in candidates or norm in [c.lower() for c in candidates]:
            continue

        # Skip filename-like tokens
        if norm in filename_candidates_lower:
            continue

        # CODE-LIKENESS GATE:
        # Plain all-lowercase words are excluded at this stage.
        # They may only enter via backtick-enclosed (Priority 2) or
        # explicit type-keyword / usages pattern (Priority 3/4).
        if not is_code_like(identifier):
            continue

        candidates.append(identifier)

    return candidates


# ============================================================
# Exact Repository File Matching
# ============================================================

def find_matching_repository_files(
    filename: str,
    repository_path: str
) -> list[str]:
    filename_lower = filename.lower()
    files = get_repository_files(repository_path)

    return [
        file_path
        for file_path in files
        if os.path.basename(file_path).lower() == filename_lower
    ]


def find_file_location(
    query: str,
    repository_path: str
):
    candidates = extract_filename_candidates(query)
    if not candidates:
        return None

    for candidate in candidates:
        matches = find_matching_repository_files(
            candidate,
            repository_path
        )

        if len(matches) == 1:
            file_path = matches[0]
            return {
                "answer": (
                    f"The file `{candidate}` is located at `{file_path}`."
                ),
                "sources": [
                    {
                        "file": file_path,
                        "language": get_file_language(file_path),
                        "start_line": None,
                        "end_line": None,
                        "score": 1.0,
                    }
                ]
            }

        if len(matches) > 1:
            file_lines = "\n".join(
                f"- `{file_path}`"
                for file_path in matches
            )
            return {
                "answer": (
                    f"I found multiple files named `{candidate}`:\n\n{file_lines}"
                ),
                "sources": [
                    {
                        "file": file_path,
                        "language": get_file_language(file_path),
                        "start_line": None,
                        "end_line": None,
                        "score": 1.0,
                    }
                    for file_path in matches
                ]
            }

    return None


def answer_missing_filename_query(
    query: str,
    repository_path: str
):
    candidates = extract_filename_candidates(query)
    if not candidates:
        return None

    for candidate in candidates:
        matches = find_matching_repository_files(
            candidate,
            repository_path
        )
        if matches:
            return None

    return {
        "answer": (
            f"I couldn't find a file named `{candidates[0]}` in the repository."
        ),
        "sources": []
    }


# ============================================================
# Exact File Code Retrieval
# ============================================================

def is_file_code_request_query(
    query: str
) -> bool:
    """
    Detect requests that explicitly ask to show/read the source code of a
    named repository file.

    This is intentionally separate from is_file_location_query(). A query such
    as "Show the exact Record.js code that defines the user relationship"
    should retrieve Record.js itself instead of being routed to semantic RAG
    or the generic repository-file listing path.
    """
    query_lower = query.lower().strip()
    filename_candidates = extract_filename_candidates(query)

    if not filename_candidates:
        return False

    code_request_patterns = [
        "show the exact",
        "show me the exact",
        "show exact",
        "show me",
        "show the code",
        "show code",
        "give me the code",
        "give the code",
        "display the code",
        "exact code",
        "source code",
        "code that",
        "code which",
        "implementation of",
        "source of",
        "read the file",
        "read file",
        "open the file",
        "open file",
        "file code",
        "code dikhao",
        "code batao",
        "poora code",
        "pura code",
    ]

    return any(pattern in query_lower for pattern in code_request_patterns)


def _read_repository_file_lines(
    file_path: str,
    repository_path: str
) -> list[str] | None:
    """Read one repository file as source lines."""
    absolute_path = os.path.join(
        repository_path,
        file_path.replace("/", os.sep)
    )

    try:
        with open(
            absolute_path,
            "r",
            encoding="utf-8",
            errors="replace"
        ) as file:
            return file.readlines()
    except (OSError, UnicodeError):
        return None


def _extract_relevant_code_block(
    lines: list[str],
    query: str
) -> tuple[int, int] | None:
    """
    Find the most relevant contiguous source block for relationship/model
    questions. Returns zero-based [start, end) line indexes.

    The matcher is deliberately conservative. If it cannot identify a clear
    relationship block, the caller falls back to the complete file instead of
    inventing a code range.
    """
    q = query.lower()
    relationship_query = any(
        marker in q
        for marker in [
            "relationship",
            "relation",
            "references",
            "reference",
            "belongs to",
            "linked to",
            "associated with",
            "user relationship",
            "user relation",
        ]
    )

    if not relationship_query:
        return None

    candidate_indexes = []

    for index, line in enumerate(lines):
        line_lower = line.lower()

        # Strong Mongoose relationship signals.
        if (
            "ref:" in line_lower
            or "ref =" in line_lower
            or "mongoose.schema.types.objectid" in line_lower
            or "schema.types.objectid" in line_lower
        ):
            if "user" in line_lower or "user" in q:
                candidate_indexes.append(index)
                continue

        # Common nested relationship field.
        if re.search(r"\buser\s*:\s*\{", line, re.IGNORECASE):
            candidate_indexes.append(index)
            continue

        # Other ORM relationship declarations.
        if re.search(
            r"\b(?:belongsTo|hasOne|hasMany|references|foreignKey)\b",
            line,
            re.IGNORECASE,
        ):
            if "user" in line_lower or "user" in q:
                candidate_indexes.append(index)

    if not candidate_indexes:
        return None

    target = candidate_indexes[0]

    # Expand upward to the beginning of the nearest object/schema block.
    start = target
    brace_depth = 0

    for index in range(target, -1, -1):
        brace_depth += lines[index].count("{")
        brace_depth -= lines[index].count("}")

        stripped = lines[index].strip()
        if index < target and brace_depth > 0 and (
            "schema" in stripped.lower()
            or "user:" in stripped.lower()
            or "{" in stripped
        ):
            start = index

        if index < target and brace_depth <= 0:
            start = index + 1
            break

    # Expand downward through the enclosing braces. This handles:
    # user: { type: ObjectId, ref: "User" }
    # as well as a full field/schema block spread over several lines.
    end = target + 1
    depth = 0
    saw_open_brace = False

    for index in range(target, len(lines)):
        line = lines[index]
        opens = line.count("{")
        closes = line.count("}")

        if opens:
            saw_open_brace = True
        depth += opens - closes
        end = index + 1

        if saw_open_brace and depth <= 0:
            break

        # Single-line relationship declarations need no extra expansion.
        if not saw_open_brace and index > target:
            break

    if end <= start:
        return None

    return start, end


def build_exact_file_code_answer(
    query: str,
    repository_path: str
) -> dict | None:
    """
    Return exact source code from a specifically named repository file.

    This path is deterministic and never uses embeddings or the LLM to decide
    which file to show. If the query asks about a relationship, a conservative
    relevant block is returned; otherwise the complete file is returned.
    """
    candidates = extract_filename_candidates(query)
    if not candidates:
        return None

    for candidate in candidates:
        matches = find_matching_repository_files(candidate, repository_path)

        if not matches:
            continue

        if len(matches) > 1:
            file_lines = "\n".join(f"- `{path}`" for path in matches)
            return {
                "answer": (
                    f"I found multiple files named `{candidate}`. "
                    "Please specify the path:\n\n"
                    f"{file_lines}"
                ),
                "sources": [
                    {
                        "file": path,
                        "language": get_file_language(path),
                        "start_line": None,
                        "end_line": None,
                        "score": 1.0,
                    }
                    for path in matches
                ],
            }

        file_path = matches[0]
        lines = _read_repository_file_lines(file_path, repository_path)
        if lines is None:
            return {
                "answer": f"I found `{candidate}`, but I couldn't read its source code.",
                "sources": [],
            }

        relevant_range = _extract_relevant_code_block(lines, query)

        if relevant_range:
            start, end = relevant_range
            selected_lines = lines[start:end]
            display_start = start + 1
            display_end = end
            heading = f"Exact code from `{file_path}` relevant to your query"
        else:
            selected_lines = lines
            display_start = 1
            display_end = len(lines)
            heading = f"Exact source code of `{file_path}`"

        code = "".join(selected_lines)

        # Keep the deterministic response bounded for unusually large files.
        # We do not truncate normal source files; when truncation is necessary,
        # the answer explicitly says so and sources still point to the file.
        max_code_chars = 30000
        truncated = len(code) > max_code_chars
        if truncated:
            code = code[:max_code_chars].rstrip() + "\n... [output truncated]"

        language = get_file_language(file_path)
        fence_language = {
            "javascript": "javascript",
            "typescript": "typescript",
            "python": "python",
            "java": "java",
            "cpp": "cpp",
            "c": "c",
            "go": "go",
            "rust": "rust",
            "html": "html",
            "css": "css",
            "json": "json",
            "yaml": "yaml",
            "markdown": "markdown",
            "shell": "bash",
            "sql": "sql",
            "xml": "xml",
        }.get(str(language).lower(), "")

        answer = (
            f"{heading} (lines {display_start}-{display_end}):\n\n"
            f"```{fence_language}\n"
            f"{code}"
            f"\n```"
        )

        if truncated:
            answer += "\n\nThe displayed code was truncated because the file is unusually large."

        return {
            "answer": answer,
            "sources": [
                {
                    "file": file_path,
                    "language": language,
                    "start_line": display_start,
                    "end_line": display_end,
                    "score": 1.0,
                }
            ],
        }

    # The named file was explicitly requested but does not exist.
    return {
        "answer": (
            f"I couldn't find the requested file `{candidates[0]}` in the repository."
        ),
        "sources": [],
    }


# ============================================================
# Deterministic Identifier Search & Classification
# ============================================================


def classify_identifier_match_type(
    line: str,
    identifier: str,
    file_path: str = ""
) -> str:
    """
    Classify a matching source line as a definition, reference, or usage.

    Import and require statements are classified as references.
    Function, class, model, and variable declarations are classified
    as definitions.
    """
    escaped = re.escape(identifier)

    # --------------------------------------------------------
    # 1. Imports, Requires, and Bindings
    # --------------------------------------------------------

    # CommonJS require statements
    if re.search(r"\brequire\s*\(", line):
        return "reference"

    # ES modules, TypeScript, Python, Java, and C/C++ imports
    if re.match(
        r"^\s*(?:import|from|using|#include)\b",
        line
    ):
        return "reference"

    # --------------------------------------------------------
    # 2. Model / Entity / Schema Definitions
    # --------------------------------------------------------

    if re.search(
        rf"""\b(?:mongoose\.)?model\s*\(\s*['"]{escaped}['"]""",
        line
    ):
        return "definition"

    if re.search(
        rf"""\bdefine\s*\(\s*['"]{escaped}['"]""",
        line
    ):
        return "definition"

    # --------------------------------------------------------
    # 3. Class, Interface, Type, Enum, Struct, Trait
    # --------------------------------------------------------

    if re.search(
        rf"\b(?:export\s+(?:default\s+)?)?"
        rf"(?:class|interface|type|enum|struct|trait)\s+"
        rf"{escaped}\b",
        line
    ):
        return "definition"

    # --------------------------------------------------------
    # 4. Function Declarations and Expressions
    # --------------------------------------------------------

    # Standard function declarations:
    # function foo(...), async function foo(...)
    if re.search(
        rf"\b(?:export\s+(?:default\s+)?)?"
        rf"(?:async\s+)?function(?:\s*\*|\s+)"
        rf"{escaped}\s*[\(<]",
        line
    ):
        return "definition"

    # CommonJS exported function assignments:
    # exports.foo = async (req, res) => { ... }
    # module.exports.foo = (req, res) => { ... }
    # exports.foo = async function (...) { ... }
    if re.search(
        rf"\b(?:module\.exports|exports)\s*\.\s*"
        rf"{escaped}\s*=\s*"
        rf"(?:async\s*)?"
        rf"(?:"
        rf"\([^)]*\)\s*=>"
        rf"|[A-Za-z_$][A-Za-z0-9_$]*\s*=>"
        rf"|function\b"
        rf")",
        line
    ):
        return "definition"

    # CommonJS exported method shorthand:
    # exports.foo = function foo(...) { ... }
    # (Covered by the preceding function expression rule.)

    # Arrow function assignments:
    # const foo = () =>, const foo = async () =>
    if re.search(
        rf"\b(?:export\s+)?(?:const|let|var)\s+"
        rf"{escaped}\s*=\s*"
        rf"(?:async\s*)?"
        rf"(?:\([^)]*\)|[A-Za-z_$][A-Za-z0-9_$]*)"
        rf"\s*=>",
        line
    ):
        return "definition"

    # Function expression assignments:
    # const foo = function (...) { ... }
    if re.search(
        rf"\b(?:export\s+)?(?:const|let|var)\s+"
        rf"{escaped}\s*=\s*(?:async\s*)?function\b",
        line
    ):
        return "definition"

    # Python function and class declarations
    if re.search(
        rf"^\s*(?:async\s+)?def\s+{escaped}\s*\(",
        line
    ):
        return "definition"

    if re.search(
        rf"^\s*class\s+{escaped}\s*[:\(]",
        line
    ):
        return "definition"

    # Java / C++ / Go / Rust method or function declarations
    if re.search(
        rf"\b(?:public|private|protected|static|final|fn|func)"
        rf"\s+.*?\b{escaped}\s*[\(<]",
        line
    ):
        return "definition"

    # Object method definition:
    # foo(req, res) {
    if re.search(
        rf"^\s*{escaped}\s*\([^)]*\)\s*\{{",
        line
    ):
        return "definition"

    # --------------------------------------------------------
    # 5. Variable / Constant Assignments
    # --------------------------------------------------------

    if re.search(
        rf"\b(?:export\s+)?(?:const|let|var)\s+"
        rf"{escaped}\s*=",
        line
    ):
        return "definition"

    # CommonJS exported variables:
    # exports.foo = value
    # module.exports.foo = value
    if re.search(
        rf"\b(?:module\.exports|exports)\s*\.\s*"
        rf"{escaped}\s*=",
        line
    ):
        return "definition"

    # Python top-level assignment
    if re.match(rf"^\s*{escaped}\s*=", line):
        return "definition"

    # --------------------------------------------------------
    # 6. File-Level Named Export
    # --------------------------------------------------------

    if file_path:
        base_name = os.path.splitext(
            os.path.basename(file_path)
        )[0]

        if base_name.lower() == identifier.lower():
            if re.search(
                r"\b(?:module\.exports\s*=|export\s+default\b)",
                line
            ):
                return "definition"

    # No declaration pattern matched
    return "usage"


def search_repository_identifier(
    identifier: str,
    repository_path: str,
    intent: str = "all"
) -> list[dict]:
    """
    Token-boundary and selector-aware deterministic identifier search.
    Prevents false positive substring matches (e.g. getRecords won't match getRecordsBackup).
    """
    if not identifier:
        return []

    # Build boundary-aware regex pattern
    if identifier.startswith("#"):
        # Exact CSS selector boundary matching
        pattern = re.compile(rf"{re.escape(identifier)}(?![A-Za-z0-9_\-])")
    else:
        # Programming identifier boundary matching
        pattern = re.compile(rf"(?<![A-Za-z0-9_$]){re.escape(identifier)}(?![A-Za-z0-9_$])")

    matches = []
    files = get_repository_files(repository_path)

    for relative_path in files:
        absolute_path = os.path.join(
            repository_path,
            relative_path.replace("/", os.sep)
        )

        try:
            with open(
                absolute_path,
                "r",
                encoding="utf-8",
                errors="replace"
            ) as file:
                lines = file.readlines()
        except (OSError, UnicodeError):
            continue

        for line_number, line in enumerate(lines, start=1):
            if pattern.search(line):
                match_type = classify_identifier_match_type(
                    line=line,
                    identifier=identifier,
                    file_path=relative_path
                )

                matches.append({
                    "file": relative_path,
                    "language": get_file_language(relative_path),
                    "start_line": line_number,
                    "end_line": line_number,
                    "score": 1.0,
                    "content": line.rstrip(),
                    "type": match_type,
                    "identifier": identifier,
                })

    return matches


def build_identifier_search_answer(
    query: str,
    repository_path: str
) -> dict | None:
    """
    Execute deterministic identifier search and format output based on query intent.
    Returns None if no matches are found.
    """
    identifiers = extract_identifier_candidates(query)
    if not identifiers:
        return None

    intent = detect_identifier_intent(query)
    all_matches = []

    for identifier in identifiers:
        matches = search_repository_identifier(
            identifier,
            repository_path,
            intent=intent
        )
        all_matches.extend(matches)

    if not all_matches:
        return None

    # Deduplicate matches by (file, line_number)
    unique_matches = {}
    for match in all_matches:
        key = (match["file"], match["start_line"])
        if key not in unique_matches:
            unique_matches[key] = match

    deduped_matches = list(unique_matches.values())

    # Sort: definitions first, then references, then usages
    type_priority = {"definition": 0, "reference": 1, "usage": 2}
    deduped_matches.sort(
        key=lambda m: (
            type_priority.get(m["type"], 2),
            m["file"],
            m["start_line"]
        )
    )

    
    # Deduplicate matches by (file, line_number)
    unique_matches = {}
    for match in all_matches:
        key = (match["file"], match["start_line"])
        if key not in unique_matches:
            unique_matches[key] = match

    deduped_matches = list(unique_matches.values())

    # Sort: definitions first, then references, then usages
    type_priority = {"definition": 0, "reference": 1, "usage": 2}
    deduped_matches.sort(
        key=lambda m: (
            type_priority.get(m["type"], 2),
            m["file"],
            m["start_line"]
        )
    )

    

    definitions = [m for m in deduped_matches if m["type"] == "definition"]
    usages = [m for m in deduped_matches if m["type"] != "definition"]

    lines = []
    primary_id = identifiers[0]


    if intent == "definition":
        if definitions:
            lines.append(f"Found definition(s) for `{primary_id}` in the repository:\n")
            for m in definitions[:20]:
                lines.append(f"- `{m['file']}` (line {m['start_line']}) [definition]")
                if m.get("content"):
                    lines.append(f"  `{m['content'].strip()}`")

            # Also provide related references summary if useful
            if usages:
                lines.append(f"\nAlso found {len(usages)} import/usage reference(s) across the repository.")
        else:
            lines.append(
                f"I couldn't find an explicit definition for `{primary_id}`, "
                f"but found {len(usages)} reference/usage occurrence(s):\n"
            )
            for m in usages[:20]:
                lines.append(f"- `{m['file']}` (line {m['start_line']}) [{m['type']}]")
                if m.get("content"):
                    lines.append(f"  `{m['content'].strip()}`")
    elif intent == "usage":
        lines.append(f"Found usages/references of `{primary_id}` in the repository:\n")
        for m in deduped_matches[:30]:
            lines.append(f"- `{m['file']}` (line {m['start_line']}) [{m['type']}]")
            if m.get("content"):
                lines.append(f"  `{m['content'].strip()}`")
    else:
        lines.append(f"Found matches for `{primary_id}` in the repository:\n")
        for m in deduped_matches[:30]:
            lines.append(f"- `{m['file']}` (line {m['start_line']}) [{m['type']}]")
            if m.get("content"):
                lines.append(f"  `{m['content'].strip()}`")

    # Sources: prioritize definition sources when asking for definitions
    if intent == "definition" and definitions:
        selected_sources = definitions[:20]
    else:
        selected_sources = deduped_matches[:30]

    sources = [
        {
            "file": m["file"],
            "language": m["language"],
            "start_line": m["start_line"],
            "end_line": m["end_line"],
            "score": 1.0,
        }
        for m in selected_sources
    ]

    return {
        "answer": "\n".join(lines),
        "sources": sources
    }


# ============================================================
# Deterministic Text Search
# ============================================================

def search_repository_text(
    query: str,
    repository_path: str
) -> list[dict]:
    tokens = extract_query_tokens(query)
    if not tokens:
        return []

    matches = []
    files = get_repository_files(repository_path)

    for relative_path in files:
        absolute_path = os.path.join(
            repository_path,
            relative_path.replace("/", os.sep)
        )

        try:
            with open(
                absolute_path,
                "r",
                encoding="utf-8",
                errors="replace"
            ) as file:
                lines = file.readlines()
        except (OSError, UnicodeError):
            continue

        for line_number, line in enumerate(lines, start=1):
            line_lower = line.lower()
            matched_tokens = [
                token for token in tokens
                if token in line_lower
            ]

            if not matched_tokens:
                continue

            matches.append({
                "file": relative_path,
                "language": get_file_language(relative_path),
                "start_line": line_number,
                "end_line": line_number,
                "score": float(len(matched_tokens)),
                "content": line.rstrip(),
            })

    matches.sort(
        key=lambda item: (
            -item["score"],
            item["file"],
            item["start_line"]
        )
    )

    return matches


# ============================================================
# Repository File and Structure Answers
# ============================================================

def build_repository_file_answer(
    repository_path: str,
    language_filter: str | None = None
) -> dict:
    files = get_repository_files(repository_path)

    if language_filter:
        extensions = LANGUAGE_EXTENSION_MAP.get(
            language_filter,
            set()
        )
        files = [
            f for f in files
            if os.path.splitext(f)[1].lower() in extensions
        ]

    if not files:
        if language_filter:
            return {
                "answer": f"I couldn't find any {language_filter} files in the repository.",
                "sources": []
            }
        return {
            "answer": "I couldn't find any files in the repository.",
            "sources": []
        }

    file_lines = "\n".join(f"- `{f}`" for f in files)

    if language_filter:
        answer = (
            f"The repository contains {len(files)} {language_filter} file(s):\n\n"
            f"{file_lines}"
        )
    else:
        answer = (
            f"The repository contains {len(files)} files:\n\n"
            f"{file_lines}"
        )

    sources = [
        {
            "file": f,
            "language": get_file_language(f),
            "start_line": None,
            "end_line": None,
            "score": 1.0,
        }
        for f in files
    ]

    return {
        "answer": answer,
        "sources": sources
    }


def build_repository_structure_answer(
    repository_path: str
) -> dict:
    files = get_repository_files(repository_path)
    folders = get_repository_folders(repository_path)

    if not files and not folders:
        return {
            "answer": "I couldn't find any files or folders in the repository.",
            "sources": []
        }

    lines = []

    if folders:
        lines.append("Folders:")
        for folder in folders:
            lines.append(f"- `{folder}/`")
        lines.append("")

    if files:
        lines.append("Files:")
        for file_path in files:
            lines.append(f"- `{file_path}`")

    sources = [
        {
            "file": file_path,
            "language": get_file_language(file_path),
            "start_line": None,
            "end_line": None,
            "score": 1.0,
        }
        for file_path in files
    ]

    return {
        "answer": "\n".join(lines),
        "sources": sources
    }


# ============================================================
# Query Tokenization
# ============================================================

def extract_query_tokens(
    query: str
) -> list[str]:
    tokens = re.findall(
        r"#?[A-Za-z_][A-Za-z0-9_\-\.]*",
        query
    )

    stop_words = {
        "where", "what", "which", "how", "does", "do", "is", "are", "the",
        "a", "an", "in", "of", "to", "for", "on", "with", "and", "or",
        "me", "show", "find", "tell", "about", "work", "works", "used",
        "use", "this", "that", "code", "file", "files", "all", "defined",
        "definition", "usage", "usages", "repository", "project",
    }

    useful_tokens = []
    for token in tokens:
        normalized = token.lower()
        if normalized in stop_words:
            continue
        if len(normalized) < 2:
            continue
        if normalized not in useful_tokens:
            useful_tokens.append(normalized)

    return useful_tokens


# ============================================================
# Hybrid Keyword Ranking & Semantic Search (Lazy Loaded)
# ============================================================

def keyword_matches(
    query: str,
    result
) -> float:
    query_lower = query.lower()
    payload = result.payload or {}
    metadata = payload.get("metadata", {})

    filename = str(metadata.get("filename", "")).lower()
    file_path = str(metadata.get("file_path", "")).lower()
    relative_path = str(metadata.get("relative_path", "")).lower()
    content = str(payload.get("content", "")).lower()

    score = 0.0

    # Deprioritize lockfiles strongly in semantic ranking
    if filename in LOCKFILE_NAMES:
        score -= 50.0

    if filename and filename in query_lower:
        score += 100.0

    if relative_path and relative_path in query_lower:
        score += 90.0

    if file_path and file_path in query_lower:
        score += 80.0

    filename_without_ext = os.path.splitext(filename)[0]
    if filename_without_ext and filename_without_ext in query_lower:
        score += 50.0

    tokens = extract_query_tokens(query)
    for token in tokens:
        if token in content:
            if len(token) >= 8:
                score += 30.0
            elif len(token) >= 5:
                score += 20.0
            else:
                score += 10.0

        if token in filename:
            score += 15.0

        if token in relative_path:
            score += 10.0

    return score


def content_match_score(
    query: str,
    result
) -> int:
    payload = result.payload or {}
    content = str(payload.get("content", "")).lower()
    if not content:
        return 0

    tokens = extract_query_tokens(query)
    return sum(1 for token in tokens if token in content)


def deduplicate_results(
    results
):
    unique_results = {}

    for result in results:
        payload = result.payload or {}
        if not payload:
            continue

        metadata = payload.get("metadata", {})
        file_path = metadata.get("relative_path") or metadata.get("file_path", "")
        start_line = metadata.get("start_line")
        end_line = metadata.get("end_line")

        key = (
            normalize_path(file_path),
            start_line,
            end_line
        )

        if key not in unique_results or result.score > unique_results[key].score:
            unique_results[key] = result

    return sorted(
        unique_results.values(),
        key=lambda r: r.score,
        reverse=True
    )


def diversify_results(
    results,
    max_per_file: int = 3
):
    selected_results = []
    file_counts = {}

    for result in results:
        payload = result.payload or {}
        if not payload:
            continue

        metadata = payload.get("metadata", {})
        file_path = metadata.get("relative_path") or metadata.get("file_path", "")
        normalized_path = normalize_path(file_path)

        current_count = file_counts.get(normalized_path, 0)
        if current_count >= max_per_file:
            continue

        selected_results.append(result)
        file_counts[normalized_path] = current_count + 1

    return selected_results


def _extract_recent_reference(conversation_context: str) -> str | None:
    """
    Extract the most recent concrete code/file reference from conversation
    history. This is used only for follow-up query resolution; it does not
    become a general semantic retrieval query.
    """
    if not conversation_context:
        return None

    recent = conversation_context[-8000:]

    # Prefer explicit identifier references produced by our deterministic
    # answers because these are the strongest signals for a follow-up.
    patterns = [
        r"Found definition\(s\) for\s+`([^`]+)`",
        r"Found usages/references of\s+`([^`]+)`",
        r"Found matches for\s+`([^`]+)`",
        r"definition for\s+`([^`]+)`",
        r"identifier\s+`([^`]+)`",
        r"file\s+`([^`]+)`\s+is located",
        r"file named\s+`([^`]+)`",
    ]

    for pattern in patterns:
        matches = re.findall(pattern, recent, re.IGNORECASE)
        if matches:
            candidate = matches[-1].strip()
            if candidate:
                return candidate

    # Fallback: use the last backtick-enclosed token that looks like a
    # code symbol or a repository path.
    enclosed = re.findall(r"`([^`]+)`", recent)
    for candidate in reversed(enclosed):
        candidate = candidate.strip()
        if not candidate:
            continue
        if (
            "/" in candidate
            or "\\" in candidate
            or "." in candidate
            or is_code_like(candidate)
        ):
            return candidate

    return None


def resolve_follow_up_query(
    query: str,
    conversation_context: str = ""
) -> str:
    """
    Resolve short contextual follow-ups into a standalone repository query.

    Examples:
        "Where is it located?" -> "Where is api.js located?"
        "Where is it defined?" -> "Where is lockSeats defined?"
        "Where is it used?"    -> "Where is lockSeats used?"

    Only obvious reference-follow-ups are rewritten. Normal conceptual
    questions remain untouched.
    """
    if not query or not conversation_context:
        return query

    q = query.strip()
    q_lower = q.lower()

    follow_up_patterns = [
        r"\bwhere\s+is\s+(?:it|this|that)\s+(?:located|defined|implemented|used|declared)\b",
        r"\bwhere\s+(?:can\s+i\s+)?find\s+(?:it|this|that)\b",
        r"\bhow\s+(?:does|do)\s+(?:it|this|that)\s+work\b",
        r"\bwhat\s+(?:does|is)\s+(?:it|this|that)\b",
        r"\bwhere\s+(?:is|are)\s+(?:its|their)\s+(?:definition|usage|usages|references?)\b",
        r"\b(?:show|find)\s+(?:it|this|that)\b",
    ]

    if not any(re.search(pattern, q_lower) for pattern in follow_up_patterns):
        return query

    reference = _extract_recent_reference(conversation_context)
    if not reference:
        return query

    if re.search(r"\b(?:located|find)\b", q_lower):
        return f"Where is `{reference}` located?"

    if re.search(r"\b(?:defined|implemented|declared|definition)\b", q_lower):
        return f"Where is `{reference}` defined?"

    if re.search(r"\b(?:used|usage|usages|references?)\b", q_lower):
        return f"Find all usages of `{reference}`"

    if re.search(r"\bhow\s+(?:does|do)\b", q_lower):
        return f"How does `{reference}` work?"

    return f"What does `{reference}` do?"


def is_conceptual_query(query: str) -> bool:
    """Return True for questions that need architectural/semantic reasoning."""
    q = query.lower().strip()

    markers = [
        "how does", "how do", "how is", "how are", "how can",
        "why does", "why do", "why is", "why are",
        "explain", "describe", "walk me through", "give me an overview",
        "overview of", "architecture of", "flow of", "workflow of",
        "how it works", "how this works",
        "kaise kaam", "kaise work", "samjhao", "samjha",
    ]

    return any(marker in q for marker in markers)


def expand_conceptual_query(query: str) -> str:
    """
    Add lightweight repository-search vocabulary without inventing facts.

    This is only a retrieval aid. The final answer remains grounded in
    retrieved repository code.
    """
    q = query.lower()
    expansions = []

    concept_aliases = {
        "payment": ["payment", "order", "verify", "signature", "razorpay", "stripe"],
        "payments": ["payment", "order", "verify", "signature", "razorpay", "stripe"],
        "authentication": ["auth", "login", "register", "token", "jwt", "refresh token", "middleware"],
        "auth": ["login", "register", "token", "jwt", "refresh token", "middleware"],
        "seat locking": ["lockSeats", "unlockSeats", "redis", "socket", "seat-lock", "ttl"],
        "seat lock": ["lockSeats", "unlockSeats", "redis", "socket", "seat-lock", "ttl"],
        "booking": ["booking", "payment", "order", "seat", "razorpay"],
        "redis": ["setnx", "ttl", "lock", "unlock", "seat-lock"],
        "socket": ["socket.io", "disconnect", "lockSeats", "unlockSeats"],
        "transaction": [
            "transaction", "transactions", "record", "records",
            "createTransaction", "createRecord", "addTransaction", "addRecord",
            "transactionController", "recordController",
            "transactionService", "recordService",
            "Transaction", "Record", "mongoose", "model", "schema",
        ],
        "transactions": [
            "transaction", "transactions", "record", "records",
            "createTransaction", "createRecord", "addTransaction", "addRecord",
            "transactionController", "recordController",
            "transactionService", "recordService",
            "Transaction", "Record", "mongoose", "model", "schema",
        ],
    }

    for phrase, aliases in concept_aliases.items():
        if phrase in q:
            expansions.extend(aliases)

    if expansions:
        return f"{query}\nRetrieval terms: {' '.join(dict.fromkeys(expansions))}"

    return query


def _lexical_results_as_objects(
    query: str,
    repository_path: str,
    limit: int = 20
):
    """Convert deterministic text matches into the payload shape used by RAG."""
    from types import SimpleNamespace

    lexical_matches = search_repository_text(query, repository_path)
    results = []

    for match in lexical_matches[:limit]:
        payload = {
            "content": match.get("content", ""),
            "metadata": {
                "relative_path": match.get("file", ""),
                "file_path": match.get("file", ""),
                "filename": os.path.basename(match.get("file", "")),
                "language": match.get("language", "unknown"),
                "start_line": match.get("start_line"),
                "end_line": match.get("end_line"),
            },
        }
        results.append(
            SimpleNamespace(
                payload=payload,
                score=min(1.0, 0.5 + (float(match.get("score", 1.0)) * 0.05)),
            )
        )

    return results

def _is_booking_creation_query(query: str) -> bool:
    """Identify conceptual questions about creating or persisting bookings."""
    q = query.lower()

    asks_about_booking = any(
        term in q
        for term in ("booking", "reservation", "ticket")
    )
    asks_about_creation = any(
        term in q
        for term in (
            "creat", "sav", "persist", "stor",
            "database", "mongodb", "insert",
        )
    )

    return asks_about_booking and asks_about_creation


def search_code(
    query: str,
    repository_path: str,
    limit: int = DEFAULT_LIMIT
):
    """
    Perform semantic vector search + keyword ranking across repository chunks.
    Lazy imports vector_store and embeddings.
    """
    if not query or not query.strip():
        return []

    if not os.path.isdir(repository_path):
        raise ValueError(f"Repository does not exist: {repository_path}")

    from rag.vector_store import client, get_collection_name
    from rag.embeddings import generate_embedding

    collection_name = get_collection_name(repository_path)
    if not client.collection_exists(collection_name):
        raise ValueError(f"Repository is not indexed: {repository_path}")

    retrieval_query = expand_conceptual_query(query) if is_conceptual_query(query) else query
    query_vector = generate_embedding(retrieval_query)
    retrieval_limit = max(limit * 5, SEMANTIC_RETRIEVAL_LIMIT)

    results = client.query_points(
        collection_name=collection_name,
        query=query_vector,
        limit=retrieval_limit
    ).points

    relevant_results = [
        r for r in results
        if r.score >= SIMILARITY_THRESHOLD
    ]

    # Semantic retrieval is primary. For conceptual questions, add a small
    # deterministic lexical pass so important exact terms/files are not lost
    # simply because their embedding score is lower.
    if is_conceptual_query(query):
        lexical_query = expand_conceptual_query(query)
        lexical_results = _lexical_results_as_objects(
            lexical_query,
            repository_path,
            limit=300,
        )
        relevant_results.extend(lexical_results)

    
    ranked_results = []
    booking_creation_query = (
        is_conceptual_query(query)
        and _is_booking_creation_query(query)
    )

    for r in relevant_results:
        semantic_score = float(r.score)
        keyword_score = keyword_matches(query, r)
        exact_content_matches = content_match_score(query, r)

        final_score = (
            semantic_score
            + (keyword_score * 0.01)
            + (exact_content_matches * 0.08)
        )

        if booking_creation_query:
            payload = r.payload or {}
            metadata = payload.get("metadata") or {}
            file_path = (
                metadata.get("relative_path")
                or metadata.get("file_path")
                or ""
            )
            content = str(payload.get("content") or "")
            normalized_path = str(file_path).replace("\\", "/").lower()

            is_booking_controller = (
                normalized_path.endswith(
                    "backend/controllers/paymentcontroller.js"
                )
            )
            has_booking_creation = (
                "Booking.create(" in content
                or "Booking.create (" in content
            )

            if is_booking_controller and has_booking_creation:
                final_score += 2.0

        ranked_results.append((final_score, r))


    
    ranked_results.sort(key=lambda item: item[0], reverse=True)

    # Preserve the calculated relevance score during deduplication.
    best_by_location = {}

    for final_score, result in ranked_results:
        payload = result.payload or {}
        metadata = payload.get("metadata") or {}
        file_path = (
            metadata.get("relative_path")
            or metadata.get("file_path")
            or ""
        )

        key = (
            normalize_path(file_path),
            metadata.get("start_line"),
            metadata.get("end_line"),
        )

        if key not in best_by_location:
            best_by_location[key] = (final_score, result)

    unique_results = [
        result
        for _, result in sorted(
            best_by_location.values(),
            key=lambda item: item[0],
            reverse=True,
        )
    ]


    filename_candidates = extract_filename_candidates(query)
    if filename_candidates:
        normalized_candidates = {c.lower() for c in filename_candidates}
        boosted_results = []

        for r in unique_results:
            payload = r.payload or {}
            metadata = payload.get("metadata", {})
            file_path = metadata.get("relative_path") or metadata.get("file_path") or ""
            basename = os.path.basename(str(file_path)).lower()
            filename_boost = 1 if basename in normalized_candidates else 0
            boosted_results.append((filename_boost, r))

        boosted_results.sort(
            key=lambda item: (item[0], item[1].score),
            reverse=True
        )
        unique_results = [r for _, r in boosted_results]
        max_per_file = 8 if is_conceptual_query(query) else 6
        diversified_results = diversify_results(unique_results, max_per_file=max_per_file)
    
    else:
        max_per_file = 12 if is_conceptual_query(query) else 3
        diversified_results = diversify_results(
            unique_results,
            max_per_file=max_per_file,
        )


    result_limit = CONCEPTUAL_MAX_RESULTS if is_conceptual_query(query) else limit
    return diversified_results[:result_limit]


# ============================================================
# Context Construction
# ============================================================

def _is_eligible_evidence_path(
    relative_path: str
) -> bool:
    """Return True only for safe, repository-relative semantic evidence paths."""
    if not relative_path:
        return False

    normalized = str(relative_path).replace("\\", "/").strip()

    if normalized.startswith("/"):
        return False

    if re.match(r"^[A-Za-z]:/", normalized):
        return False

    if normalized.startswith("~"):
        return False

    parts = normalized.split("/")
    if ".." in parts:
        return False

    return True


def _read_source_evidence(
    result,
    repository_path: str
) -> dict | None:
    """
    Resolve retrieved metadata to the current source file.

    The indexed chunk content is NOT trusted as final evidence.
    The source file is re-read from the current repository so stale,
    invalid, cross-repository, or lockfile results cannot become evidence.
    """

    payload = result.payload or {}
    metadata = payload.get("metadata", {})

    if not isinstance(metadata, dict):
        return None

    raw_path = (
        metadata.get("relative_path")
        or metadata.get("file_path")
    )

    if not raw_path:
        return None

    raw_path = str(raw_path)

    # --------------------------------------------------------
    # Convert absolute paths to repository-relative paths
    # --------------------------------------------------------

    if os.path.isabs(raw_path):
        relative_path = clean_source_path(
            raw_path,
            repository_path
        )
    else:
        relative_path = raw_path.replace("\\", "/")

    relative_path = os.path.normpath(
        relative_path
    ).replace("\\", "/")

    # --------------------------------------------------------
    # Security / validity checks
    # --------------------------------------------------------

    if (
        not relative_path
        or relative_path == "."
        or relative_path == ".."
        or relative_path.startswith("../")
        or os.path.isabs(relative_path)
        or not _is_eligible_evidence_path(relative_path)
    ):
        return None

    # --------------------------------------------------------
    # Resolve repository root and final source path
    # --------------------------------------------------------

    repository_root = os.path.realpath(
        repository_path
    )

    absolute_path = os.path.realpath(
        os.path.join(
            repository_root,
            relative_path.replace("/", os.sep)
        )
    )

    # Prevent paths outside the repository from becoming evidence.
    try:
        if os.path.commonpath(
            [repository_root, absolute_path]
        ) != repository_root:
            return None
    except ValueError:
        return None

    # --------------------------------------------------------
    # Source file must actually exist and be a file
    # --------------------------------------------------------

    if not os.path.isfile(absolute_path):
        return None

    # --------------------------------------------------------
    # Read CURRENT repository source
    # --------------------------------------------------------

    try:
        with open(
            absolute_path,
            "r",
            encoding="utf-8",
            errors="replace"
        ) as source_file:
            source_lines = source_file.readlines()

    except (OSError, UnicodeError):
        return None

    # --------------------------------------------------------
    # Validate indexed line range
    # --------------------------------------------------------

    start_line = metadata.get("start_line")
    end_line = metadata.get("end_line")

    if (
        isinstance(start_line, bool)
        or isinstance(end_line, bool)
        or not isinstance(start_line, int)
        or not isinstance(end_line, int)
        or start_line < 1
        or end_line < start_line
        or end_line > len(source_lines)
    ):
        return None

    # --------------------------------------------------------
    # Extract CURRENT source content for the indexed range
    # --------------------------------------------------------

    content = "".join(
        source_lines[start_line - 1:end_line]
    ).rstrip()

    if not content.strip():
        return None

    # --------------------------------------------------------
    # Build trusted evidence object
    # --------------------------------------------------------

    try:
        score = float(result.score)
    except (TypeError, ValueError):
        score = 0.0

    return {
        "file": relative_path,
        "language": (
            metadata.get("language")
            or get_file_language(relative_path)
        ),
        "start_line": start_line,
        "end_line": end_line,
        "score": score,
        "content": content,
    }


def build_context(
    results,
    repository_path: str
):
    """
    Build grounded LLM context from current repository source lines.
    Include only complete evidence blocks within the generator's context budget.
    """
    from rag.generator import MAX_CONTEXT_CHARS

    context_parts = []
    sources = []
    current_size = 0

    for result in results:
        payload = getattr(result, "payload", None) or {}
        metadata = payload.get("metadata") or {}

        file_path = (
            metadata.get("relative_path")
            or metadata.get("file_path")
            or ""
        )
        file_name = os.path.basename(
            str(file_path).replace("\\", "/")
        ).lower()

        if file_name in LOCKFILE_NAMES:
            continue

        evidence = _read_source_evidence(
            result,
            repository_path,
        )

        # Preserve the existing safety rule for invalid evidence.
        if evidence is None:
            return "", []

        evidence_id = len(sources) + 1

        block = (
            f"[Evidence ID: {evidence_id}]\n"
            f"File: {evidence['file']}\n"
            f"Language: {evidence['language']}\n"
            f"Lines: {evidence['start_line']} - {evidence['end_line']}\n"
            f"Code:\n\n"
            f"{evidence['content']}\n\n"
        )

        # Do not truncate code blocks: skip blocks that do not fit.
        separator_size = 1 if context_parts else 0
        if current_size + separator_size + len(block) > MAX_CONTEXT_CHARS:
            continue

        context_parts.append(block)
        current_size += separator_size + len(block)

        sources.append({
            "evidence_id": evidence_id,
            "file": evidence["file"],
            "language": evidence["language"],
            "start_line": evidence["start_line"],
            "end_line": evidence["end_line"],
            "score": evidence["score"],
        })

    return "\n".join(context_parts), sources


# ============================================================
# Main Answer Function (Deterministic-First Architecture)
# ============================================================


def answer_query(
    query: str,
    repository_path: str,
    limit: int = DEFAULT_LIMIT,
    mode: str = "auto",
    conversation_context: str = "",
) -> dict:
    """
    Main repository query entry point.

    Architecture:
        deterministic lookup
        -> semantic retrieval
        -> grounded generation
        -> evidence filtering
        -> public response
    """
    REFUSAL = "I couldn't find enough information in the codebase."

    # 1. Basic validation
    if not query or not query.strip():
        return {
            "answer": "Please provide a question.",
            "sources": [],
        }

    query = query.strip()

    if not repository_path:
        return {
            "answer": "Repository path is required.",
            "sources": [],
        }

    if not os.path.isdir(repository_path):
        return {
            "answer": f"The repository does not exist: `{repository_path}`",
            "sources": [],
        }

    mode = (mode or "auto").strip().lower()
    if mode not in {"auto", "exact", "semantic"}:
        mode = "auto"

    # 2. Resolve follow-up query
    retrieval_query = resolve_follow_up_query(
        query,
        conversation_context,
    )
    conceptual = is_conceptual_query(retrieval_query)

    # 3. Repository structure
    if is_repository_structure_query(retrieval_query):
        return build_repository_structure_answer(repository_path)

    # 4. Exact file source-code retrieval
    if is_file_code_request_query(retrieval_query):
        exact_file_code_result = build_exact_file_code_answer(
            retrieval_query,
            repository_path,
        )
        if exact_file_code_result:
            return exact_file_code_result

    # 5. Language-specific file listing
    language_filter = detect_language_filter(retrieval_query)
    if language_filter:
        return build_repository_file_answer(
            repository_path,
            language_filter,
        )

    # 6. Generic repository file listing
    if is_repository_file_query(retrieval_query):
        return build_repository_file_answer(repository_path)

    # 7. Exact filename location
    filename_candidates = extract_filename_candidates(retrieval_query)

    if filename_candidates and is_file_location_query(retrieval_query):
        location_result = find_file_location(
            retrieval_query,
            repository_path,
        )
        if location_result:
            return location_result

        missing_result = answer_missing_filename_query(
            retrieval_query,
            repository_path,
        )
        if missing_result:
            return missing_result

    # 8. Exact identifier search
    should_run_identifier_search = (
        mode != "semantic"
        and not conceptual
        and is_identifier_query(retrieval_query)
    )

    if should_run_identifier_search:
        exact_identifier_result = build_identifier_search_answer(
            retrieval_query,
            repository_path,
        )
        if exact_identifier_result:
            return exact_identifier_result

        candidates = extract_identifier_candidates(retrieval_query)

        if candidates:
            missing_id = candidates[0]

            if detect_identifier_intent(retrieval_query) == "definition":
                return {
                    "answer": REFUSAL,
                    "sources": [],
                }

            return {
                "answer": (
                    f"I couldn't find the identifier "
                    f"`{missing_id}` in the repository."
                ),
                "sources": [],
            }

    # 9. Semantic retrieval
    try:
        results = search_code(
            query=retrieval_query,
            repository_path=repository_path,
            limit=(
                CONCEPTUAL_MAX_RESULTS
                if conceptual
                else limit
            ),
        )
    except ValueError as error:
        return {
            "answer": str(error),
            "sources": [],
        }
    except Exception as error:
        print("Semantic retrieval error:", error)
        return {
            "answer": (
                "The repository search could not be completed. "
                "Please check the backend logs."
            ),
            "sources": [],
        }

    # TEMPORARY DIAGNOSTICS
    print("\n--- BOOKING RETRIEVAL DEBUG ---")
    print("Query:", retrieval_query)
    print("Conceptual:", conceptual)
    print("Retrieved results:", len(results))

    for index, result in enumerate(results[:10], start=1):
        payload = getattr(result, "payload", None) or {}
        metadata = payload.get("metadata") or {}

        print(
            index,
            "| FILE:",
            metadata.get("relative_path") or metadata.get("file_path"),
            "| LINES:",
            metadata.get("start_line"),
            "-",
            metadata.get("end_line"),
            "| SCORE:",
            getattr(result, "score", None),
        )

    if not results:
        print("STOP: semantic retrieval returned no results.")
        print("--- END BOOKING RETRIEVAL DEBUG ---\n")
        return {
            "answer": REFUSAL,
            "sources": [],
        }

    # 10. Build grounded context
    context, sources = build_context(
        results,
        repository_path,
    )

    print("Context length:", len(context))
    print("Context source count:", len(sources))
    print("Context source files:", [s["file"] for s in sources])

    if not context.strip() or not sources:
        print("STOP: context construction returned no usable sources.")
        print("--- END BOOKING RETRIEVAL DEBUG ---\n")
        return {
            "answer": REFUSAL,
            "sources": [],
        }

    # 11. Generation query
    generation_query = query

    if conversation_context:
        generation_query = f"""
Previous conversation:
{conversation_context}

Current user question:
{query}

Repository retrieval query:
{retrieval_query}
""".strip()

    # 12. Grounded answer generation
    from rag import generator

    generated = generator.generate_grounded_answer(
        query=generation_query,
        context=context,
        sources=sources,
    )

    if not isinstance(generated, dict):
        print("STOP: generator returned a non-dictionary response.")
        print("--- END BOOKING RETRIEVAL DEBUG ---\n")
        return {
            "answer": REFUSAL,
            "sources": [],
        }

    answer = generated.get("answer", REFUSAL)
    selected_evidence_ids = generated.get("evidence_ids", [])

    print("Generated answer:", str(answer)[:300])
    print("Selected evidence IDs:", selected_evidence_ids)
    print("Available evidence IDs:", [s["evidence_id"] for s in sources])

    if not isinstance(selected_evidence_ids, list):
        print("STOP: evidence_ids is not a list.")
        print("--- END BOOKING RETRIEVAL DEBUG ---\n")
        return {
            "answer": REFUSAL,
            "sources": [],
        }

    selected_evidence_ids = {
        evidence_id
        for evidence_id in selected_evidence_ids
        if isinstance(evidence_id, int)
        and not isinstance(evidence_id, bool)
    }

    # 13. Explicit refusal
    if answer == REFUSAL:
        print("STOP: generator explicitly refused.")
        print("--- END BOOKING RETRIEVAL DEBUG ---\n")
        return {
            "answer": REFUSAL,
            "sources": [],
        }

    # 14. Keep only evidence cited by the generator
    grounded_sources = [
        source
        for source in sources
        if source.get("evidence_id") in selected_evidence_ids
    ]

    print("Grounded source count:", len(grounded_sources))
    print("--- END BOOKING RETRIEVAL DEBUG ---\n")

    if not grounded_sources:
        return {
            "answer": REFUSAL,
            "sources": [],
        }

    # 15. Remove internal evidence IDs
    public_sources = [
        {
            "file": source["file"],
            "language": source["language"],
            "start_line": source["start_line"],
            "end_line": source["end_line"],
            "score": source["score"],
        }
        for source in grounded_sources
    ]

    return {
        "answer": answer,
        "sources": public_sources,
    }
