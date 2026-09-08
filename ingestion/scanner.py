import os


SUPPORTED_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".java",
    ".cpp",
    ".c",
    ".go",
    ".rs",
}


IGNORED_DIRECTORIES = {
    ".git",
    "node_modules",
    ".venv",
    "__pycache__",
    "dist",
    "build",
}


def scan_repository(repository_path: str):
    files = []

    for root, directories, filenames in os.walk(repository_path):
        directories[:] = [
            directory
            for directory in directories
            if directory not in IGNORED_DIRECTORIES
        ]

        for filename in filenames:
            extension = os.path.splitext(filename)[1].lower()

            if extension in SUPPORTED_EXTENSIONS:
                file_path = os.path.join(root, filename)
                files.append(file_path)

    return files


def read_file(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8") as file:
        return file.read()


def get_file_metadata(file_path: str):
    filename = os.path.basename(file_path)
    extension = os.path.splitext(filename)[1].lower()

    language_map = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".java": "java",
        ".cpp": "cpp",
        ".c": "c",
        ".go": "go",
        ".rs": "rust",
    }

    return {
        "file_path": file_path,
        "filename": filename,
        "extension": extension,
        "language": language_map.get(extension, "unknown"),
    }


if __name__ == "__main__":
    repository_path = "data/monetrik-financesystem"

    files = scan_repository(repository_path)

    print(f"Total files found: {len(files)}")

    for file in files:
        print(file)

    print("\n--- First File Content ---\n")

    content = read_file(files[0])
    print(content)

    metadata = get_file_metadata(files[0])

    print("\n--- File Metadata ---\n")
    print(metadata)