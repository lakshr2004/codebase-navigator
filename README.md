# Codebase Navigator

Codebase Navigator scans a local repository or a validated GitHub repository,
creates deterministic text and JavaScript route chunks, and indexes them in a
repository-specific Qdrant collection for code search and grounded answers.

## Ingestion policy

The scanner includes supported source, configuration, and documentation files.
It skips binary files, invalid UTF-8 files, unreadable files, symbolic links,
and generated or dependency directories including `.git`, `node_modules`,
`.venv`, `venv`, `__pycache__`, `.pytest_cache`, `dist`, `build`, and `coverage`.
Nested repositories are scanned for source files, but their `.git` metadata is
never traversed. Scan output uses sorted repository-relative paths with `/`
separators.

## Safety configuration

All values are environment variables with safe defaults:

| Variable | Default | Purpose |
|---|---:|---|
| `MAX_FILE_SIZE_BYTES` | `10485760` | Maximum source file size |
| `MAX_INDEXED_FILES` | `25000` | Maximum supported files in one scan |
| `MAX_DIRECTORY_DEPTH` | `50` | Maximum repository-relative file depth |
| `MAX_LINE_SIZE_BYTES` | `1048576` | Maximum UTF-8 source line size |
| `GITHUB_CLONE_TIMEOUT_SECONDS` | `300` | Git clone timeout |
| `QDRANT_PATH` | `data/qdrant` | Local Qdrant storage path |

Oversized, malformed, binary, or unreadable files are skipped and reported via
the application logger. Invalid repository paths and empty supported content
are fatal indexing errors. Git clone failures use temporary destinations and
clean up partial clones.

Private/authenticated GitHub repositories are not handled by the application
itself. Use a credentialed Git environment outside this application or provide
a public repository URL.

## Current status

The repository is still Beta / Needs Hardening. Phase 1 hardening is tested
locally, but symlink behavior requires CI coverage on an environment that can
create symlinks, and live GitHub/network behavior is covered only through
controlled subprocess tests.
