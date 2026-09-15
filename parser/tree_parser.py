import os
import sys
import logging

sys.path.append(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

from tree_sitter import Language, Parser
import tree_sitter_javascript as tsjavascript

from ingestion.scanner import (
    scan_repository,
    read_file,
    get_file_metadata,
)


# ============================================================
# Tree-sitter JavaScript Setup
# ============================================================

JS_LANGUAGE = Language(
    tsjavascript.language()
)

parser = Parser(JS_LANGUAGE)
logger = logging.getLogger(__name__)


# ============================================================
# Constants
# ============================================================

SUPPORTED_EXTENSIONS = {
    ".js",
    ".jsx",
}

SUPPORTED_HTTP_METHODS = {
    "get",
    "post",
    "put",
    "patch",
    "delete",
}


# ============================================================
# Helpers
# ============================================================

def get_node_text(node) -> str:
    """
    Safely convert a Tree-sitter node into UTF-8 text.
    """

    return node.text.decode(
        "utf-8",
        errors="replace"
    )


# ============================================================
# Route Extraction
# ============================================================

def extract_routes(content: str) -> list[dict]:
    """
    Extract Express-style HTTP routes from JavaScript code.

    Supported:

        app.get(...)
        app.post(...)
        app.put(...)
        app.patch(...)
        app.delete(...)

        router.get(...)
        router.post(...)
        router.put(...)
        router.patch(...)
        router.delete(...)
    """

    tree = parser.parse(
        content.encode("utf-8")
    )

    routes = []

    def walk(node):

        if node.type == "call_expression":

            function_node = (
                node.child_by_field_name(
                    "function"
                )
            )

            if (
                function_node
                and function_node.type == "member_expression"
            ):

                property_node = (
                    function_node.child_by_field_name(
                        "property"
                    )
                )

                if not property_node:
                    return

                method = get_node_text(
                    property_node
                )

                if method not in SUPPORTED_HTTP_METHODS:
                    return

                arguments_node = (
                    node.child_by_field_name(
                        "arguments"
                    )
                )

                if not arguments_node:
                    return

                route = None
                handler = None

                for child in arguments_node.named_children:

                    # ----------------------------------------
                    # Route path
                    # ----------------------------------------

                    if child.type == "string":

                        if route is None:
                            route = (
                                get_node_text(
                                    child
                                ).strip("\"'")
                            )

                    # ----------------------------------------
                    # Handler
                    # ----------------------------------------

                    elif child.type in {
                        "identifier",
                        "arrow_function",
                        "function",
                    }:

                        handler = child

                # --------------------------------------------
                # Store route
                # --------------------------------------------

                if route and handler:

                    routes.append({
                        "type": "route",

                        "method": method.upper(),

                        "route": route,

                        "handler": get_node_text(
                            handler
                        ),

                        "start_line": (
                            node.start_point.row + 1
                        ),

                        "end_line": (
                            node.end_point.row + 1
                        ),

                        "content": get_node_text(
                            node
                        ),
                    })

        for child in node.named_children:
            walk(child)

    walk(
        tree.root_node
    )

    return routes


# ============================================================
# Repository Parser
# ============================================================

def parse_repository(
    repository_path: str
) -> list[dict]:
    """
    Parse JavaScript/JSX files from a repository
    and extract structured route information.

    Every parsed item inherits the standardized
    metadata generated by scanner.py.
    """

    files = scan_repository(
        repository_path
    )

    parsed_items = []

    for file_path in files:

        metadata = get_file_metadata(
            file_path,
            repository_path
        )

        extension = metadata.get(
            "extension",
            ""
        ).lower()

        if extension not in SUPPORTED_EXTENSIONS:
            continue

        try:

            content = read_file(
                file_path
            )

        except (OSError, UnicodeDecodeError, ValueError) as e:
            logger.warning("Skipping unreadable file %s: %s", file_path, e)

            continue

        try:
            routes = extract_routes(content)
        except (TypeError, ValueError) as e:
            logger.warning("Skipping malformed JavaScript file %s: %s", file_path, e)
            continue

        for route in routes:

            parsed_metadata = {
                **metadata,

                "type": route["type"],

                "method": route["method"],

                "route": route["route"],

                "start_line": route["start_line"],

                "end_line": route["end_line"],

                "chunk_type": "ast",
            }

            parsed_items.append({
                "content": route["content"],

                "metadata": parsed_metadata,
            })

    return parsed_items


# ============================================================
# Manual Test
# ============================================================

if __name__ == "__main__":

    repository_path = (
        "data/monetrik-financesystem"
    )

    items = parse_repository(
        repository_path
    )

    print(
        f"Total parsed items: {len(items)}"
    )

    for item in items[:10]:

        metadata = item["metadata"]

        print(
            "\n--- Parsed Item ---"
        )

        print(
            "File:",
            metadata.get("file_path")
        )

        print(
            "Relative Path:",
            metadata.get("relative_path")
        )

        print(
            "Repository:",
            metadata.get("repository_path")
        )

        print(
            "Language:",
            metadata.get("language")
        )

        print(
            "Type:",
            metadata.get("type")
        )

        print(
            "Method:",
            metadata.get("method")
        )

        print(
            "Route:",
            metadata.get("route")
        )

        print(
            "Handler:",
            item["content"]
        )

        print(
            "Lines:",
            metadata.get("start_line"),
            "-",
            metadata.get("end_line")
        )

        print(
            "Content:"
        )

        print(
            item["content"]
        )