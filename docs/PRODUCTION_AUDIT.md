# Production Audit

## Current status

The project remains **Beta / Needs Hardening**. Phase 1 implementation is
substantially hardened but is not declared production-ready.

Latest verification target:

- Full suite: 79 passed, 1 skipped, 2 warnings before the current Phase 1 additions
- Current work adds scanner, clone, and indexing regression coverage
- Symlink tests are conditionally skipped when the host cannot create symlinks

## Phase 1 policies

The scanner ignores dependency and generated directories (`.git`,
`node_modules`, `.venv`, `venv`, `__pycache__`, `.pytest_cache`, `dist`, `build`,
`coverage`, and related caches). It excludes known binary extensions, rejects
invalid UTF-8, null bytes, unreadable files, oversized files, and lines over
the configured limit. Symlinks are not followed. Nested repository source
files may be scanned, but nested `.git` metadata is not traversed.

GitHub clones are validated before invoking Git, use an owner-specific
destination, clone into a temporary directory, enforce a timeout, and clean up
failed clones. Clone error messages do not include repository URLs or process
output.

Indexing isolates malformed documents and chunks. Existing vectors are not
deleted until all embeddings have been generated successfully. Re-indexing uses
deterministic point IDs and replaces the repository collection.

## Configuration

| Variable | Default | Enforcement |
|---|---:|---|
| `MAX_FILE_SIZE_BYTES` | `10485760` | Scanner file-size checks |
| `MAX_INDEXED_FILES` | `25000` | `scan_repository` |
| `MAX_DIRECTORY_DEPTH` | `50` | Scanner traversal and file depth |
| `MAX_LINE_SIZE_BYTES` | `1048576` | Incremental scanner decoding |
| `GITHUB_CLONE_TIMEOUT_SECONDS` | `300` | `subprocess.run` clone timeout |
| `QDRANT_PATH` | `data/qdrant` | Qdrant client initialization |

Positive integer settings are validated centrally in `core/config.py`. Invalid
runtime configuration is reported as a configuration error rather than being
silently accepted.

## Test coverage and limitations

Focused tests cover real temporary repositories for file filtering, depth,
line size, BOM/newline handling, late invalid UTF-8 and null bytes, deleted
files, nested repository metadata, deterministic output, clone cleanup and
timeouts, malformed documents, repeated vector insertion, and embedding
failure preservation.

Symlink escape and loop tests must execute in Linux/macOS CI or Windows with
symlink privileges. Controlled subprocess tests do not prove live network,
private-repository, or GitHub authentication behavior.

## Remaining risks

- Live GitHub/network behavior still needs CI or integration coverage.
- Qdrant upsert failure after collection replacement can still leave a partial
	new collection.
- Structured metrics and ingestion counters are not yet implemented.
- The application remains Beta / Needs Hardening.
