# Codebase Navigator API

Base URL: `http://127.0.0.1:8000`

## System

### `GET /`
Returns a service message.

Response `200`:

```json
{"message":"Codebase Navigator AI is running!"}
```

### `GET /health`
Liveness check.

Response `200`:

```json
{"status":"healthy","service":"codebase-navigator"}
```

### `GET /ready`
Runtime configuration readiness check.

Response `200` contains `status: "ready"` and `checks` for `app_env`, Groq, and Qdrant. Missing production configuration returns `503` with a `detail` string.

## Repositories

### `GET /repositories`
Lists indexed repository collections.

Response `200`:

```json
[{"name":"repo","collection_name":"codebase_chunks_repo"}]
```

### `POST /repositories/load`
Clones and indexes a public GitHub repository.

Request:

```json
{"repo_url":"https://github.com/owner/repository"}
```

Response `200`:

```json
{"message":"Repository loaded and indexed successfully","repository_path":"data/repos/owner__repository"}
```

An empty URL returns `400`. Invalid or failed clone/index operations return `500`. The backend currently does not provide application-managed private-repository authentication.

## Search and RAG

### `POST /ask`
Runs deterministic identifier/file search or semantic grounded answering depending on the query.

Request:

```json
{
  "query":"Where is loginUser defined?",
  "repository_path":"data/repos/owner__repository",
  "session_id":"browser-session"
}
```

Response `200`:

```json
{
  "query":"Where is loginUser defined?",
  "answer":"...",
  "sources":[
    {"file":"src/auth.js","language":"javascript","start_line":12,"end_line":18,"score":1.0}
  ]
}
```

Empty `query`, `repository_path`, or `session_id` returns `400`. Identifier misses and invalid repository lookups may return `404`. Unexpected processing failures return `500`.

## Conversations

### `GET /conversations/{session_id}`
Returns stored messages for a session. Empty IDs return `400`.

### `DELETE /conversations/{session_id}`
Clears stored messages for a session. Empty IDs return `400`.

## Error shape

FastAPI validation and application errors use a JSON object containing `detail`. The frontend should display `detail` when present and use a generic network message otherwise.
