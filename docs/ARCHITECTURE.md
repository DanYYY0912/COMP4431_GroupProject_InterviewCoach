# Architecture and data handling

## Executive summary

The browser sends interview and job-description requests to one local API. The API stores source chunks and session state, retrieves supporting material, validates model JSON and returns cited interview turns. Qwen and Whisper run natively so Apple Metal remains available. PostgreSQL is the normal database, with a labelled SQLite development fallback. The original procedural avatar has no external model-asset dependency. Cloud speech is optional and consented. This application targets a single local user and must not be exposed publicly without a separate security design.

## Decisions

1. **Contract first.** HTTP and WebSocket events follow `contracts/API.md`; state mutations use one backend service. Client responses are validated at the boundary.
2. **Explicit providers.** `demo` is deterministic practice scaffolding. `llama` calls a real local server. A public base checkpoint is not a trained VoxPrep adapter.
3. **Local inference.** Native llama.cpp and whisper.cpp keep Metal acceleration outside Docker. The frontend and API can be containerized separately from inference.
4. **Source isolation.** Uploaded content is bounded and quoted as data. It must not replace system instructions. Reports retain chunk identifiers and the text visible to the user.
5. **Degraded operation.** A missing microphone, speech service, model or WebGL context must surface an understandable fallback. Methodology shows which components were used.
6. **No candidate ranking.** Coaching concerns evidence and answer structure, with no personality, accent-quality or protected-trait scoring.

## Data lifecycle

Session creation requires transcript-storage consent. Job descriptions, source chunks, turns and metrics remain in the selected local database. The browser holds editable drafts during the interview. Session export is user initiated. Deletion removes the selected session and its turns. The last session referencing a job also deletes that private job profile and its chunks. A profile created during an abandoned setup can remain without a session and should be cleared before reusing the database for sensitive material. Audio used for local fallback is transmitted only to the local Whisper service and should not be retained as a normal application artifact.

Azure receives audio for recognition and question text for synthesis after cloud voice consent. Azure credentials remain server side. A browser token is temporary and held in memory. Browser/system speech availability depends on the OS and browser. Avoid speaking confidential content with a remotely backed browser voice.

## Retrieval and source policy

The assessed target is full-text search plus vector retrieval, reciprocal-rank fusion, top-12 reranking and top-four evidence. Optional services and their fallbacks are reported in health. Locally authored STAR guidance is distinct from attributed O*NET data. Uploaded instructions are untrusted even when they resemble a system message. Citation validation blocks fabricated source identifiers, but semantic support requires evaluation and human review.

## Threat and reliability boundaries

Loopback bindings and allowed-origin checks protect the classroom local application from accidental network exposure. Uploads are limited and file types validated. Database queries use SQLAlchemy. No auth is provided by design. Treat `.env`, user exports and database volumes as private. Model response timeouts and malformed JSON should preserve recoverable session state. `make demo-reset` manages only its own fixture IDs.

## Authoritative references

- [llama.cpp server API and structured output](https://raw.githubusercontent.com/ggml-org/llama.cpp/master/tools/server/README.md)
- [Docker Compose readiness and dependency order](https://docs.docker.com/compose/how-tos/startup-order/)
- [Whisper converted model provenance](https://huggingface.co/ggerganov/whisper.cpp)
- [Unsloth Qwen base quantization](https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF)

Exact model revisions, sizes and checksums are in `scripts/models.json`. Runtime dependency versions are locked separately from GPU training dependencies.
