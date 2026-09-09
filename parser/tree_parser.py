import os
import sys

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)

from tree_sitter import Language, Parser
import tree_sitter_javascript as tsjavascript

from ingestion.scanner import (
    scan_repository,
    read_file,
    get_file_metadata
)


JS_LANGUAGE = Language(tsjavascript.language())
parser = Parser(JS_LANGUAGE)


def get_node_text(node):
    return node.text.decode("utf-8")


def extract_routes(content: str) -> list[dict]:

    tree = parser.parse(content.encode("utf-8"))

    routes = []

    def walk(node):

        if node.type == "call_expression":

            function_node = node.child_by_field_name("function")

            if function_node and function_node.type == "member_expression":

                property_node = function_node.child_by_field_name("property")

                if property_node:

                    method = get_node_text(property_node)

                    if method in ["get", "post", "put", "patch", "delete"]:

                        arguments_node = node.child_by_field_name("arguments")

                        if arguments_node:

                            route = None
                            arrow_function = None

                            for child in arguments_node.children:

                                if child.type == "string":
                                    route = get_node_text(child).strip('"')

                                elif child.type == "arrow_function":
                                    arrow_function = child

                            if arrow_function:

                                routes.append({
                                    "type": "route",
                                    "method": method.upper(),
                                    "route": route,
                                    "start_line": arrow_function.start_point.row + 1,
                                    "end_line": arrow_function.end_point.row + 1,
                                    "content": get_node_text(arrow_function)
                                })

        for child in node.children:
            walk(child)

    walk(tree.root_node)

    return routes


def parse_repository(repository_path: str) -> list[dict]:

    files = scan_repository(repository_path)

    parsed_items = []

    for file_path in files:

        metadata = get_file_metadata(file_path)

        # Currently Tree-sitter JavaScript parser
        # is being used for JS/JSX files only.
        if metadata["extension"] not in [".js", ".jsx"]:
            continue

        content = read_file(file_path)

        routes = extract_routes(content)

        for route in routes:

            parsed_items.append({
                "content": route["content"],
                "metadata": {
                    **metadata,
                    "type": route["type"],
                    "method": route["method"],
                    "route": route["route"],
                    "start_line": route["start_line"],
                    "end_line": route["end_line"]
                }
            })

    return parsed_items


if __name__ == "__main__":

    repository_path = "data/monetrik-financesystem"

    items = parse_repository(repository_path)

    print(f"Total parsed items: {len(items)}")

    for item in items[:10]:

        print("\n--- Parsed Item ---")

        print("File:", item["metadata"]["file_path"])
        print("Type:", item["metadata"]["type"])
        print("Method:", item["metadata"]["method"])
        print("Route:", item["metadata"]["route"])
        print(
            "Lines:",
            item["metadata"]["start_line"],
            "-",
            item["metadata"]["end_line"]
        )

        print("Content:")
        print(item["content"])