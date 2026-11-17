# Architecture and data handling

## Executive summary

The browser sends interview and job-description requests to one local API. The API stores source chunks and session state, retrieves supporting material, validates model JSON and returns cited interview turns. Qwen and Whisper run natively so Apple Metal remains available. PostgreSQL is the normal database, with a labelled SQLite development fallback. The original procedural avatar has no external model-asset dependency. Inference can use the four servers selected in Settings; choosing external servers sends the corresponding task inputs to them. This application targets a single local user and must not be exposed publicly without a separate security design.

## Decisions

1. **Contract first.** HTTP and WebSocket events follow `contracts/API.md`; state mutations use one backend service. Client responses are validated at the boundary.
2. **Explicit providers.** `demo` is deterministic practice scaffolding. `llama` calls a local server; `openai` calls the Agent selected in Settings. A public base checkpoint is not a trained VoxPrep adapter.
3. **Local inference.** Native llama.cpp and whisper.cpp keep Metal acceleration outside Docker. The frontend and API can be containerized separately from inference.
4. **Source isolation.** Uploaded content is bounded and quoted as data. It must not replace system instructions. Reports retain chunk identifiers and the text visible to the user.
5. **Degraded operation.** A missing microphone, speech service, model or WebGL context must surface an understandable fallback. Health and reports identify active providers and fallbacks.
6. **No candidate ranking.** Coaching concerns evidence and answer structure, with no personality, accent-quality or protected-trait scoring.

## Data lifecycle

Starting an interview stores its session and transcript locally by default. The setup page collects a job description and interview options, with a read-only status summary; there is no separate storage checkbox. Job descriptions, source chunks, turns and metrics remain in the selected local database. The browser holds editable drafts during the interview. Session export is user initiated. Deletion removes the selected session and its turns. The last session referencing a job also deletes that private job profile and its chunks. A profile created during an abandoned setup can remain without a session and should be cleared before reusing the database for sensitive material. Audio goes through the local backend to the configured ASR server, or to local Whisper when ASR is blank. It is not retained as a normal application artifact. Agent receives prompts and answer excerpts; embedding/reranking servers receive source passages and queries. These services can be external when configured by the user.

Question playback uses only local browser/system voices. Availability depends on the OS and browser; typed interaction remains available when no local voice is installed.

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

## Runtime inference settings

The Settings tab replaces the original methodology page. Four independent connections select Agent, ASR, Embedding and Reranker with a base URL, optional key and model. The evaluation endpoint and recorded methodology files remain available for assessment.

Settings persist on the server with owner-only file permissions, using atomic replacement. Public settings responses expose only whether a key exists. A retained key is tied to its previous URL; changing destinations requires a new or explicitly empty key. Saving updates new requests without a restart. Changing the embedding connection invalidates cached vectors, and retrieval reindexes relevant sources. Non-1024-dimensional vectors use the JSON/cosine path because the existing pgvector index has 1024 dimensions.

The browser talks only to the local API. The backend makes authenticated requests to configured services without following redirects. Model discovery can fail independently of saving; manual model IDs remain supported. The application still validates generated citations and transcript evidence. It falls back visibly if a model rejects a request or returns invalid output.

Protocol references: [OpenAI transcription format](https://developers.openai.com/api/reference/resources/audio/subresources/transcriptions/methods/create), [OpenAI embedding format](https://developers.openai.com/api/reference/resources/embeddings/methods/create), and [vLLM compatible interfaces including rerank](https://docs.vllm.ai/en/latest/serving/online_serving/).
