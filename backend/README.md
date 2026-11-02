# VoxPrep HK backend

## Executive summary

The FastAPI service persists local job descriptions, session turns and transcript evidence. It supports an explicit deterministic demonstration provider and a local llama.cpp provider for questions and STAR reports, with schema validation and visible fallbacks. English and Cantonese interviews share one state machine over HTTP and WebSocket. Sources remain local; only user-authorized Azure speech requests leave the machine. SQLAlchemy uses SQLite for quick development or PostgreSQL with pgvector. Model reports validate exact transcript excerpts and source IDs; deterministic reports use documented keyword heuristics. Neither path is a validated or fine-tuned assessment without the separate training and evaluation evidence.

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
| `MODEL_PROVIDER` | `demo` or `llama` |
| `LLAMA_BASE_URL` | `http://127.0.0.1:8080/v1` |
| `MODEL_NAME` | `Qwen3-4B-Instruct-2507` |
| `MODEL_TIMEOUT_SECONDS`, `REPORT_TIMEOUT_SECONDS` | 45 and 110 seconds; model failures become visible fallbacks |
| `EMBEDDING_BASE_URL` | Empty = lexical fallback; use local `http://127.0.0.1:8082/v1` |
| `EMBEDDING_DIMENSIONS` | 1024, matching the migration's vector column |
| `RERANKER_BASE_URL` | Optional local service exposing `/rerank` with query/documents/results indices |
| `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION` | Optional server-held Speech credentials |
| `WHISPER_BASE_URL` | `http://127.0.0.1:8081`; enable whisper-server `--convert` and FFmpeg for browser audio |
| `ALLOWED_ORIGINS` | localhost/127.0.0.1 on ports 5173 and 8000 |

Run `.venv/bin/python -m app.index_knowledge` to embed all source chunks after configuring an embedding service. The PostgreSQL migration installs the vector extension and HNSW/full-text indexes. Models accept only local service hosts, including `host.docker.internal`, to preserve transcript privacy.

## Verification and semantics

```sh
.venv/bin/pytest backend/tests -q
.venv/bin/ruff check backend
```

HTTP answer submissions should include the optional current `turn_id` to reject stale/replayed answers. A simultaneous second submission receives 409. Pause/cancel/end interrupt pending generation without committing the draft. Retry reopens the last submitted answer and removes later turns. Skip advances without fabricating an answer. Deleting the last session for a job also deletes its private job text. History accepts bounded `limit` and `offset` query parameters.

WebSocket text deltas are chunks of an already validated completed model response, not raw first-token streaming. Raw model JSON is never rendered. Model timeouts, invalid schemas, unsupported competency names and fabricated citation IDs trigger the visible `demo-fallback` provider. Model reports require exact transcript substrings and allowed source IDs, cache validated output, and invalidate the cache after edits. Their limitations explain model generation or heuristic fallback, context truncation and unavailable speech measurements. Excerpt identity checks cannot prove semantic entailment; assessors must review citation precision.

For bounded context, generation uses relevant source excerpts while displayed citations preserve the entire original chunk. Reports analyze up to 160 word/CJK/punctuation units (at most 1,000 characters) per answer; truncation is disclosed. The report output budget is 1,400 tokens and a 110-second timeout. These are recovery bounds, not claims that latency targets have been met.

## Official references

- [FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/)
- [llama.cpp server API and JSON schema output](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)
- [pgvector Python and SQLAlchemy integration](https://github.com/pgvector/pgvector-python)
- [Azure Speech token authentication](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/rest-text-to-speech)
- [O*NET 31.0 license](https://www.onetcenter.org/license_db.html)
