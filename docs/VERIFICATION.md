# Implementation verification

## Executive summary

The application has passed controlled automated checks and real local-service smoke tests on this Mac. These checks establish runnable software and integration behavior. They do not establish the plan's fine-tuning, human-review, speech-quality, latency or usability thresholds. Final source validation includes code through `0100c70` plus the comparison browser test. Logs under `artifacts/verification/` remain on the development Mac; distributable synthetic raw service evidence is retained under `evaluation/raw/`.

## Controlled checks

| Check | Observed result on 2026-11-02 | Scope / evidence |
| --- | --- | --- |
| Python | 61 passed | API, ingestion, schemas, retrieval, model failures, token boundary, dataset/evaluation metrics, adapter packaging and safe migrations; `artifacts/verification/python-tests-final.log` |
| Frontend | 23 passed | Setup, schemas, audio/draft cancellation, session-response races, comparison, complete exports and methodology; frontend commits `48558f6` and `bb46906` |
| Static checks | Passed | Ruff, ESLint, TypeScript and production frontend build |
| Browser | 5 passed | English/Cantonese completion and report export, mobile dashboard/setup, pause/resume/reload/skip/retry, denied microphone, deletion, comparison and full transcript export; `artifacts/verification/e2e-comparison-final.log`, Playwright/axe |
| Dependency audit | No high or critical frontend findings | One moderate development-only minimatch advisory remains through lint tooling; Vitest worker vulnerability removed |
| Database | Real PostgreSQL/pgvector plus SQLite tests | Migrations, HNSW/vector and full-text indexes, 11 knowledge chunks indexed; source-isolated cleanup |
| Docker | Build and isolated container passed | UI without browser errors; both-language three-answer/report/delete flows; foreign-origin rejection; native services reachable through `host.docker.internal`; `evaluation/raw/docker_container_smoke.json` |
| Deck | 8 slides rendered and visually inspected | Artifact Tool finalizer validation passed; receipt retained under `artifacts/presentation-build/` |
| Backup video | 80.0667 seconds | Silent, accelerated scripted typed flow; deterministic provider, fictional inputs; no voice/model-quality claim |
| Source archive | Integrity and every entry hash verified | 150 project files plus submission manifest; no credentials, session databases, private transcripts, base weights or fabricated adapter; checksum beside the ZIP |

Automated axe checks are a limited accessibility check, not a complete WCAG certification. Upstream deprecation/annotation warnings do not fail the current tests or build. CI is configured but has not been executed on a remote GitHub runner.

## Real local service diagnostics

The downloaded artifacts are pinned by immutable revisions, sizes and SHA-256 in `scripts/models.json`. Synthetic integration inputs are explicitly marked and are not drawn from a held-out reviewed benchmark.

- **English Qwen:** a complete three-answer session used real `llama` turns and a model-generated report. First complete turn: **18.285 s**; report request: **74.116 s**. These are individual development timings with concurrent work, not p95 or first-token measurements.
- **Cantonese Qwen:** the initial integration exposed fabricated near-match citation IDs and honestly used fallback. Per-request allowed-ID schemas fixed the failure. The final complete three-answer flow used `llama` for all questions and the report: first complete turn **23.396 s**, report **65.135 s**. Earlier failures and direct component probes are retained alongside the final run in `evaluation/raw/`.
- **Retrieval:** actual local embeddings and reranking were connected to PostgreSQL. A two-document reranker probe placed the relevant document first. The separate 40-query lexical/SQLite diagnostic had recall@5 1.0, with no citation-precision labels. That easy synthetic fixture is not the assessed RAG result.
- **Whisper:** English and Cantonese system-generated speech reached the real local recognizer. English text was recognizable; Cantonese output mixed traditional/simplified characters and altered wording. No human speaker, WER/CER or accuracy claim is made.
- **Azure:** not configured. Deterministic token/audio integration tests are not real service verification.

The current validated-buffer approach waits for a complete model turn before sending display chunks. Do not claim the four-second first-token or eight-second speech-end-to-audio target has passed. Avatar FPS, real Azure viseme interruption and final-machine latency remain to be measured.

## Honest scope of the delivered materials

The 1,500 curriculum examples are synthetic drafts: 900 English, 450 Cantonese and 150 mixed-language examples, across the prescribed task proportions. They have **zero completed human reviews**. Template similarities deliberately block promotion until examples are rewritten and reviewed. Training on these drafts is not an authorized shortcut around the review gates.

No adapter, training log, loss curve, base-versus-LoRA preference result or participant study has been invented. GPU scripts and evaluated metric implementations prepare that work; they do not substitute for it. Two team identities and the proposed responsibility table are present, with two placeholders and actual contribution evidence still required.

The original procedural avatar substitutes for the planned VRM asset. Evaluation runs are stored as JSON artifacts rather than database entities. True upstream model-token streaming is pending. The presentation and source package disclose these implementation limits.
