import os
import re
import sys

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

SIMILARITY_THRESHOLD = 0.05
DEFAULT_LIMIT = 10
MAX_CONTEXT_CHARS = 24000

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


def is_identifier_query(
    query: str
) -> bool:
    """
    Detect if the query is an exact identifier search/definition/usage/existence query.
    Distinguishes exact identifier lookups from conceptual/explanatory questions.
    """
    query_lower = query.lower().strip()

    # If query is asking for general repository file or folder structure
    if is_repository_structure_query(query) or is_repository_file_query(query):
        return False

    # Check for direct existence query for a specific identifier:
    # "Does getRecordsBackup exist?", "Is there a getRecord identifier?", "Does increaseScore exist?"
    existence_patterns = [
        r"\bdoes\s+[`'\"]?([A-Za-z_$][A-Za-z0-9_$]*)[`'\"]?\s+exist\b",
        r"\bis\s+there\s+(?:a\s+|an\s+)?[`'\"]?([A-Za-z_$][A-Za-z0-9_$]*)[`'\"]?\s+(?:identifier|function|class|variable|symbol|component)?\b",
        r"\b(?:check\s+if|see\s+if)\s+[`'\"]?([A-Za-z_$][A-Za-z0-9_$]*)[`'\"]?\s+exists?\b",
    ]
    for p in existence_patterns:
        if re.search(p, query_lower):
            return True

    # Conceptual question prefixes that should route to semantic RAG
    # unless explicitly asking for definition/location/usages
    conceptual_markers = [
        "how does",
        "how do",
        "how to",
        "how is",
        "how can",
        "why does",
        "why is",
        "why do",
        "does this",
        "does the",
        "is there",
        "explain",
        "describe",
        "overview of",
        "what does",
        "tell me about",
        "kaise kaam",
        "kaise karta",
        "samjhao",
    ]

    is_conceptual = any(
        query_lower.startswith(marker) or f" {marker} " in f" {query_lower} "
        for marker in conceptual_markers
    )

    if is_conceptual:
        # Check if it has an explicit definition command like "where is X defined"
        if not re.search(r"\b(?:where is|kaha defined|find all usages of)\b", query_lower):
            return False

    # Explicit identifier query patterns
    patterns = [
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

    return any(pattern in query_lower for pattern in patterns)


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
    Preserves exact casing and handles camelCase, PascalCase, snake_case, $id, and #id.
    """
    candidates = []

    # 1. CSS selectors such as #pannel-bottom or #main-header
    css_selectors = re.findall(
        r"#[A-Za-z_][A-Za-z0-9_\-]*",
        query
    )
    for selector in css_selectors:
        if selector not in candidates:
            candidates.append(selector)

    # 2. Backtick or quote enclosed symbols
    enclosed = re.findall(r"[`'\"]([A-Za-z_$][A-Za-z0-9_$]*)['\"`]", query)
    for symbol in enclosed:
        if symbol not in candidates:
            candidates.append(symbol)

    # 3. Programming identifiers
    identifiers = re.findall(
        r"\b[A-Za-z_$][A-Za-z0-9_$]*\b",
        query
    )

    filename_candidates_lower = {
        c.lower() for c in extract_filename_candidates(query)
    }

    # Common English and Hinglish stop words that are not code identifiers
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

    for identifier in identifiers:
        norm = identifier.lower()

        if norm in stop_words:
            continue

        if len(identifier) < 2:
            continue

        # If it matches a filename base or filename, skip
        if norm in filename_candidates_lower:
            continue

        if identifier not in candidates and norm not in [c.lower() for c in candidates]:
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
# Deterministic Identifier Search & Classification
# ============================================================

def classify_identifier_match_type(
    line: str,
    identifier: str,
    file_path: str = ""
) -> str:
    """
    Accurately classify whether a line contains a definition, reference/import, or usage.
    Crucially ensures import/require lines (e.g. const User = require(...)) are classified
    as 'reference' and NOT 'definition'.
    """
    escaped = re.escape(identifier)

    # --------------------------------------------------------
    # 1. Imports, Requires, and Bindings (ALWAYS 'reference')
    # --------------------------------------------------------
    # CommonJS require statements: const User = require("..."), require("./User")
    if re.search(r"\brequire\s*\(", line):
        return "reference"

    # ES6 / TypeScript / Python / Java import statements:
    # import User from "...", import { User } from "...", from models import User
    if re.match(r"^\s*(?:import|from|using|#include)\b", line):
        return "reference"

    # --------------------------------------------------------
    # 2. Model / Entity / Schema Definitions
    # --------------------------------------------------------
    # Mongoose / ORM model definitions: mongoose.model("User", ...), model('User', ...)
    if re.search(rf"""\b(?:mongoose\.)?model\s*\(\s*['"]{escaped}['"]""", line):
        return "definition"

    # Sequelize / ORM define: db.define("User", ...)
    if re.search(rf"""\bdefine\s*\(\s*['"]{escaped}['"]""", line):
        return "definition"

    # --------------------------------------------------------
    # 3. Class, Interface, Type, Enum, Struct, Trait Definitions
    # --------------------------------------------------------
    if re.search(rf"\b(?:export\s+(?:default\s+)?)?(?:class|interface|type|enum|struct|trait)\s+{escaped}\b", line):
        return "definition"

    # --------------------------------------------------------
    # 4. Function Declarations & Expressions
    # --------------------------------------------------------
    # Standard function declaration: function foo(, async function foo(, export function foo(
    if re.search(rf"\b(?:export\s+(?:default\s+)?)?(?:async\s+)?function(?:\s*\*|\s+){escaped}\s*[\(<]", line):
        return "definition"

    # Arrow function or function expression assignment:
    # const foo = () =>, const foo = async () =>, export const foo = function()
    if re.search(rf"\b(?:export\s+)?(?:const|let|var)\s+{escaped}\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][A-Za-z0-9_$]*)\s*=>", line):
        return "definition"
    if re.search(rf"\b(?:export\s+)?(?:const|let|var)\s+{escaped}\s*=\s*(?:async\s*)?function\b", line):
        return "definition"

    # Python def and class
    if re.search(rf"^\s*(?:async\s+)?def\s+{escaped}\s*\(", line):
        return "definition"
    if re.search(rf"^\s*class\s+{escaped}\s*[:\(]", line):
        return "definition"

    # Java / C++ / Go / Rust method or function declaration
    if re.search(rf"\b(?:public|private|protected|static|final|fn|func)\s+.*?\b{escaped}\s*[\(<]", line):
        return "definition"

    # Object method definition: foo(req, res) {
    if re.search(rf"^\s*{escaped}\s*\([^)]*\)\s*\{{", line):
        return "definition"

    # --------------------------------------------------------
    # 5. Variable / Constant Assignments (Non-Import)
    # --------------------------------------------------------
    # const MAX_LIMIT = 500, let counter = 0
    if re.search(rf"\b(?:export\s+)?(?:const|let|var)\s+{escaped}\s*=", line):
        return "definition"

    # Python top-level assignment
    if re.match(rf"^{escaped}\s*=", line):
        return "definition"

    # --------------------------------------------------------
    # 6. File-Level Named Export
    # --------------------------------------------------------
    if file_path:
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        if base_name.lower() == identifier.lower():
            if re.search(r"\b(?:module\.exports\s*=|export\s+default\b)", line):
                return "definition"

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

    query_vector = generate_embedding(query)
    retrieval_limit = max(limit * 5, 30)

    results = client.query_points(
        collection_name=collection_name,
        query=query_vector,
        limit=retrieval_limit
    ).points

    relevant_results = [
        r for r in results
        if r.score >= SIMILARITY_THRESHOLD
    ]

    ranked_results = []
    for r in relevant_results:
        semantic_score = float(r.score)
        keyword_score = keyword_matches(query, r)
        exact_content_matches = content_match_score(query, r)

        final_score = (
            semantic_score
            + (keyword_score * 0.01)
            + (exact_content_matches * 0.08)
        )
        ranked_results.append((final_score, r))

    ranked_results.sort(key=lambda item: item[0], reverse=True)
    ordered_results = [r for _, r in ranked_results]
    unique_results = deduplicate_results(ordered_results)

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
        diversified_results = diversify_results(unique_results, max_per_file=6)
    else:
        diversified_results = diversify_results(unique_results, max_per_file=3)

    return diversified_results[:limit]


# ============================================================
# Context Construction
# ============================================================

def build_context(
    results,
    repository_path: str
):
    context_parts = []
    sources = []
    current_size = 0

    for result in results:
        payload = result.payload or {}
        if not payload:
            continue

        metadata = payload.get("metadata", {})
        content = str(payload.get("content", ""))
        if not content.strip():
            continue

        file_path = metadata.get("relative_path") or metadata.get("file_path") or "Unknown file"
        if not metadata.get("relative_path"):
            file_path = clean_source_path(file_path, repository_path)

        language = metadata.get("language", "unknown")
        start_line = metadata.get("start_line")
        end_line = metadata.get("end_line")

        block = (
            f"File: {file_path}\n"
            f"Language: {language}\n"
            f"Lines: {start_line} - {end_line}\n"
            f"Code:\n\n"
            f"{content}\n\n"
        )

        remaining = MAX_CONTEXT_CHARS - current_size
        if remaining <= 0:
            break

        if len(block) > remaining:
            if remaining < 500:
                break
            block = block[:remaining]

        context_parts.append(block)
        current_size += len(block)

        sources.append({
            "file": file_path,
            "language": language,
            "start_line": start_line,
            "end_line": end_line,
            "score": float(result.score),
        })

    return "\n".join(context_parts), sources


# ============================================================
# Main Answer Function (Deterministic-First Architecture)
# ============================================================

def answer_query(
    query: str,
    repository_path: str,
    limit: int = DEFAULT_LIMIT
) -> dict:
    """
    Main entry point for repository querying.

    Routing Strategy:
    1. Repository structure queries
    2. Language-specific file queries
    3. Generic repository file listing queries
    4. Exact filename location & existence queries
    5. Exact identifier search & existence queries (NO RAG fallthrough on negative)
    6. Semantic RAG for conceptual/understanding queries
    """
    if not query or not query.strip():
        return {
            "answer": "Please provide a question.",
            "sources": []
        }

    query = query.strip()

    if not repository_path:
        return {
            "answer": "Repository path is required.",
            "sources": []
        }

    if not os.path.isdir(repository_path):
        return {
            "answer": f"The repository does not exist: `{repository_path}`",
            "sources": []
        }

    # 1. Repository Structure
    if is_repository_structure_query(query):
        return build_repository_structure_answer(repository_path)

    # 2. Language-Specific Files
    language_filter = detect_language_filter(query)
    if language_filter:
        return build_repository_file_answer(repository_path, language_filter)

    # 3. Generic Repository Files
    if is_repository_file_query(query):
        return build_repository_file_answer(repository_path)

    # 4. Exact Filename Location
    filename_candidates = extract_filename_candidates(query)
    if filename_candidates and is_file_location_query(query):
        location_result = find_file_location(query, repository_path)
        if location_result:
            return location_result

        missing_result = answer_missing_filename_query(query, repository_path)
        if missing_result:
            return missing_result

    # 5. Exact Identifier Search
    # If the query is an identifier query, deterministic search MUST resolve it.
    if is_identifier_query(query):
        exact_identifier_result = build_identifier_search_answer(
            query,
            repository_path
        )
        if exact_identifier_result:
            return exact_identifier_result

        # Missing Identifier -> Return clear negative answer without hallucinating
        candidates = extract_identifier_candidates(query)
        if candidates:
            missing_id = candidates[0]
            return {
                "answer": f"I couldn't find the identifier `{missing_id}` in the repository.",
                "sources": []
            }

    # 6. Semantic RAG (For conceptual / high-level questions)
    try:
        results = search_code(
            query=query,
            repository_path=repository_path,
            limit=limit
        )
    except ValueError as error:
        return {
            "answer": str(error),
            "sources": []
        }

    if not results:
        return {
            "answer": "I couldn't find enough relevant information in the codebase.",
            "sources": []
        }

    # Build Context & Generate Answer
    context, sources = build_context(results, repository_path)
    if not context.strip():
        return {
            "answer": "I couldn't find enough relevant information in the codebase.",
            "sources": []
        }

    from rag.generator import generate_answer
    answer = generate_answer(query, context)

    return {
        "answer": answer,
        "sources": sources
    }