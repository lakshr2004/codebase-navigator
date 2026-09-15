# Production Audit

## Current status

The project remains **Beta / Needs Hardening**. Phase 1 implementation is
substantially hardened but is not declared production-ready.

Latest verification:

- Full suite: 113 passed, 9 skipped, 2 warnings
- Ingestion hardening: 20 passed, 4 skipped
- Full pipeline: 23 passed, 0 skipped
- Phase 1 closure: 11 passed, 4 skipped
- Performance checks: 2 passed
- Integration: 1 passed

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

Indexing isolates malformed documents and chunks. Re-indexing uses deterministic
point IDs and upserts in place, so an embedding or upsert failure does not delete
the previously usable index. After all upserts succeed, the scanner removes
stale point IDs for deleted source chunks. If cleanup itself fails, the completed
index remains usable and the failure is logged.

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
timeouts, malformed documents, repeated vector insertion, Qdrant insertion
failure preservation, permission behavior, and secret-safe logging.

Symlink escape and loop tests must execute in Linux/macOS CI or Windows with
symlink privileges. Controlled subprocess tests do not prove live network,
private-repository, or GitHub authentication behavior.

## Remaining risks

- Live GitHub/network behavior still needs CI or integration coverage.
- Re-indexing now upserts deterministic IDs in place, preserving the previous
	index if embedding or upsert fails; stale vectors from removed source chunks
	are not yet garbage-collected.
- GitHub private/authenticated repositories are not supported by this loader;
	callers must provide a credentialed Git environment or use a public repo.
- Lightweight structured scan counters report discovered, indexed, skipped, and
	skipped-byte totals by reason. A metrics backend is not implemented.
- Performance checks use a deterministic 200-file fixture and bounded file-count
	checks; millions-of-files and 500 MB stress runs were not performed.
- Four ingestion symlink tests, two final symlink tests, and three real-permission
	tests are environment-limited on the current Windows host.
- Frontend build verification passes. Playwright verifies app load, repository
	validation, and live FastAPI health/CORS integration. Full browser ingestion,
	exact-search, and Groq RAG flows remain NOT VERIFIED without a deterministic
	local API fixture boundary.
- Phase 2A cleanup removed only the accidental root npm lockfile and tracked
	generated `frontend/node_modules` output. Backup modules and the standalone
	`ingestion/github.py` helper remain preserved pending explicit review.
- The application remains Beta / Needs Hardening.
