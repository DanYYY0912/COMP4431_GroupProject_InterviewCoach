# VoxPrep HK backend

## Executive summary

The FastAPI service persists job descriptions, session turns and transcript evidence locally. It supports deterministic demonstration coaching, local llama.cpp, and user-configured OpenAI-compatible inference providers. Settings separately configure Agent, ASR, Embedding and Reranker services; relevant text or audio is sent to the destinations the user saves. English and Cantonese interviews share one state machine over HTTP and WebSocket. SQLAlchemy uses SQLite for development or PostgreSQL with pgvector. Model reports validate exact transcript excerpts and source IDs; deterministic reports use documented keyword heuristics. Neither path is a validated or fine-tuned assessment without separate training and evaluation evidence.

## Run

From the repository root with Python 3.12:

```sh
python3.12 -m venv .venv
.venv/bin/pip install -e 'backend[test]'
.venv/bin/alembic -c backend/alembic.ini upgrade head
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The built `frontend/dist` is served at the same endpoint if present at startup. API documentation is at `/docs`. `Settings` reads root `.env`; never commit that file. Keep one API worker for this single-user classroom app so interruption cancellation operates in one process.

## Configuration

| Variable | Default / meaning |
| --- | --- |
| `DATABASE_URL` | SQLite database in root `data/`; use `postgresql+psycopg://...` for PostgreSQL |
| `MODEL_PROVIDER` | `demo`, `llama`, or `openai`; a saved Agent override uses `openai` |
| `LLAMA_BASE_URL` | `http://127.0.0.1:8080/v1` |
| `MODEL_NAME` | `Qwen3-4B-Instruct-2507` |
| `AGENT_API_KEY` | Optional server-side bearer credential |
| `MODEL_TIMEOUT_SECONDS`, `REPORT_TIMEOUT_SECONDS` | 45 and 110 seconds; model failures become visible fallbacks |
| `EMBEDDING_BASE_URL` | Empty = lexical fallback; use local `http://127.0.0.1:8082/v1` |
| `EMBEDDING_DIMENSIONS` | Legacy default 1024; actual response dimensions are validated and recorded |
| `EMBEDDING_MODEL`, `EMBEDDING_API_KEY` | Embedding model identifier and optional bearer credential |
| `RERANKER_BASE_URL`, `RERANKER_MODEL`, `RERANKER_API_KEY` | Optional `/rerank` service, model and bearer credential |
| `ASR_BASE_URL`, `ASR_MODEL`, `ASR_API_KEY` | Optional OpenAI-compatible `/audio/transcriptions` service |
| `INFERENCE_SETTINGS_PATH` | `data/inference-settings.json`; saved overrides take precedence over environment defaults |
| `WHISPER_BASE_URL` | `http://127.0.0.1:8081`; enable whisper-server `--convert` and FFmpeg for browser audio |
| `ALLOWED_ORIGINS` | localhost/127.0.0.1 on ports 5173 and 8000 |

Run `.venv/bin/python -m app.index_knowledge` to explicitly embed all source chunks, including private job descriptions, using effective saved settings. Startup indexes only bundled public knowledge; current job chunks are indexed on use. PostgreSQL uses its 1024-dimensional vector index when compatible; other dimensions use validated cosine ranking from JSON vectors. Cache provenance includes endpoint, model and credential identity; changing providers cannot reuse stale vectors.

`GET /api/inference-settings` exposes each component's `base_url`, `model`, and `api_key_set`. `PUT` accepts all four components with `api_key`: `null` retains a key only for the same normalized destination, an empty string clears it, and another value replaces it. Empty URL and model select demo coaching, native Whisper, or disabled optional retrieval, respectively. Keys are stored server-side with atomic replacement and mode `0600`; these files must not enter version control or release archives. Saves receive `409` while inference is active, then apply without restart. Existing cached reports remain historical results.

`POST /api/inference-settings/{component}/models` discovers models using server-side bearer authentication and never changes configuration. Public endpoints require HTTPS; localhost and private LAN endpoints may use HTTP. URLs cannot contain credentials, queries or fragments, and provider redirects are disabled. Provider failures and validation errors are sanitized. Model JSON Schema rejection may trigger one JSON-mode retry within the same timeout; both responses undergo the same source and evidence validation. Configured ASR uses `en`/`zh`; native Whisper retains `en`/`yue`.

## Verification and semantics

```sh
.venv/bin/pytest backend/tests -q
.venv/bin/ruff check backend
```

HTTP answer submissions should include the optional current `turn_id` to reject stale/replayed answers. A simultaneous second submission receives 409. Pause/cancel/end interrupt pending generation without committing the draft. Retry reopens the last submitted answer and removes later turns. Skip advances without fabricating an answer. Deleting the last session for a job also deletes its private job text. History accepts bounded `limit` and `offset` query parameters.

Session creation stores transcripts in local history by default. The optional `store_transcript` field accepts only `true`; a temporary session mode is not implemented.

The optional `interviewer` field accepts `jamie` and is saved with the session. It defaults to `jamie`, including for existing sessions upgraded by migration `0003`. Pausing, resuming, and retrying preserve the selection.

WebSocket text deltas are chunks of an already validated completed model response, not raw first-token streaming. Raw model JSON is never rendered. Model timeouts, invalid schemas, unsupported competency names and fabricated citation IDs trigger the visible `demo-fallback` provider. Model reports require exact transcript substrings and allowed source IDs, cache validated output, and invalidate the cache after edits. Their limitations explain model generation or heuristic fallback, context truncation and unavailable speech measurements. Excerpt identity checks cannot prove semantic entailment; assessors must review citation precision.

For bounded context, generation uses relevant source excerpts while displayed citations preserve the entire original chunk. Reports analyze up to 160 word/CJK/punctuation units (at most 1,000 characters) per answer; truncation is disclosed. The report output budget is 1,400 tokens and a 110-second timeout. These are recovery bounds, not claims that latency targets have been met.

## Official references

- [FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/)
- [llama.cpp server API and JSON schema output](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)
- [pgvector Python and SQLAlchemy integration](https://github.com/pgvector/pgvector-python)
- [O*NET 31.0 license](https://www.onetcenter.org/license_db.html)
