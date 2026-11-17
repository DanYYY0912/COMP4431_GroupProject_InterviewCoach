# Implementation verification

## Executive summary

The application has passed controlled automated checks and real local-service smoke tests on this Mac. These checks establish runnable software and integration behavior. They do not establish the plan's fine-tuning, human-review, speech-quality, latency or usability thresholds. Current validation includes the November 18 Jamie-only 3D interviewer and staged startup progress, following the Azure removal and simplified setup. Logs under `artifacts/verification/` remain on the development Mac; distributable synthetic raw service evidence is retained under `evaluation/raw/`.

## Kelvin integration — 2026-11-18

The integration branch combines the Kaggle training workflow and evidence, Cantonese transcript conversion, language validation, PDF export and presentation updates with the Jamie version. The historical no-RAG result is marked for a rerun because its requests retained source passages. The recorded weights were unavailable for integration testing.

Checks passed with the browser using isolated SQLite and demo inference. The final image also passed the English and Cantonese interview and export journeys, startup progress, and Jamie’s speaking animation on a separate PostgreSQL Compose stack. The branch Compose file maps port 4431. The validation stack used a separate loopback port and volumes.

The 17-slide PowerPoint retains the working deck's title slide. Slides 8, 10 and 14 and their notes reflect the current interview, voice and evaluation behavior.

## Jamie 3D interviewer and startup progress — 2026-11-18

The current UI uses only Jamie, previewed in setup and persisted per session. The photo textures a shallow 3D facial surface with a real mouth aperture, eyelid deformation and restrained head movement. Mouth motion starts only after local speech playback starts; pause, stop, navigation and microphone use cancel it. Automatic question reading can be disabled. This is approximate speaking animation from one portrait, not a complete head reconstruction or phoneme-perfect lip sync.

Checks passed: **156 Python tests, 70 frontend tests and nine Playwright journeys**, plus lint, type checking and production build. The ordinary Python suite skips one optional PostgreSQL test. Mesh tests verify topology, coverage and provenance; frontend tests verify speech cancellation, duplicate-start prevention and renderer cleanup. Browser tests cover slow preparation, real canvas loading, appearance persistence, controlled speech events and accessibility. The E2E server now migrates its isolated SQLite database before starting.

Visually inspected `artifacts/verification/interview-preparation.png`, `interview-3d-speaking.png`, and the idle/speaking renderer previews. The human portrait remains recognizable, and speech opens the mouth without reverting to the primitive avatar. The lazy renderer chunk is approximately 472 KB (119 KB gzip), separate from the main UI; the mesh is approximately 32 KB. Paused/reduced-motion scenes avoid repeated geometry uploads and rendering. The scene targets roughly 30 FPS; hardware frame-time and audible voice/lip-sync quality are not established by headless tests.

Runtime inference does not use MediaPipe. Its optional preprocessing environment ran successfully on Apple Silicon; its upstream wheel metadata warning is documented in the asset guide. Source PNG, model, topology and generator hashes are retained. Python results: `artifacts/verification/jamie-python-tests.log`; build output: `jamie-frontend-build.log`.

The final source image was rebuilt and started in the actual Compose stack at **http://localhost:4431**. Both services are healthy, PostgreSQL is at migration `0003`, and all three preexisting session IDs remain present with Jamie as their default appearance. The private settings file retained its exact hash, `0600` mode and UID 1000 ownership; all four configurations remain present and API keys stay redacted. Served PNG/mesh bytes match local assets, allowed-origin checks accept port 4431, and runtime `pip check` passes. Evidence: `jamie-3d-docker-final-build.log`, `jamie-3d-docker-start.log` and `jamie-3d-docker-runtime.json` under `artifacts/verification/`.

A separate container from the final image ran with fresh SQLite and demo inference, without private settings or shared volumes. It passed startup progress, disabled duplicate start, actual WebGL rendering, changing canvas pixels under controlled speech events, stable paused/reduced-motion frames, and correct redraw after resizing to 390px and 320px. Six desktop/mobile axe scans returned no violations; there were no page errors or horizontal overflow. Evidence: `artifacts/verification/docker-interviewer-ui.log`, `docker-interviewer-ui.json` and associated Docker screenshots. These checks use controlled speech events rather than audible OS playback.

## Earlier static portrait release and port 4431 — 2026-11-18

That earlier release replaced the primitive 3D avatar with three locally bundled, fictional human portraits. The choice persists in the browser without changing the session or question. Hide/show, image failure and unavailable browser storage have regression coverage. Speech playback and microphone cancellation remain functional; Three.js and simulated mouth animation are removed.

`make test` passes **135 Python tests, 45 frontend tests and eight browser journeys**, plus lint, type checks and production build. The ordinary suite skips one optional PostgreSQL case. The new browser journey confirms that a loaded portrait survives reload, the session/question/options remain unchanged, typed text survives appearance changes, and mobile accessibility checks pass. Log: `artifacts/verification/portraits-port4431-tests.log`.

The rebuilt Docker image serves the app on **http://localhost:4431**; the previous host port 8000 is closed. The container retains internal port 8000. Native API serving, Vite's proxy, default allowed origins and helper scripts now use public port 4431. Both Compose services are healthy. Existing session counts and the private settings-file integrity matched before/after container recreation, keys remain redacted, and all three served PNGs match the selected final assets. Logs: `portraits-port4431-docker-build.log`, `portraits-port4431-docker-start.log` and `portraits-port4431-runtime.json` under `artifacts/verification/`.

An isolated container from the final portrait image was visually inspected with Alex and Sam at 1440px, and Sam at 390px and 320px. All three portrait PNGs loaded, choice persisted after reload, hide/show worked, and a typed answer advanced the interview without a canvas. All four layouts had zero axe violations and no horizontal overflow; browser page/console errors and failed requests were absent. The headless speech check observed the explicit local-voice-unavailable fallback, not audible speech. The temporary container was removed. Evidence: `artifacts/verification/portrait-container/results.json` and its four screenshots.

## Docker and setup update — 2026-11-18

The latest combined suite passes **135 Python tests, 39 frontend tests and seven Playwright journeys**, with lint, type checking and production build. One optional PostgreSQL case is skipped in the ordinary suite; it passed separately during the inference-settings work. The browser checks direct Practice entry, missing/valid setup, read-only status, absence of the removed controls/copy, both languages, recovery, history/export/comparison, all four inference forms and accessibility. Log: `artifacts/verification/azure-removal-full-test.log`.

The previous dependency-download timeout is resolved using pinned build tools/base images, persistent dependency caches, bounded retries and reduced download concurrency. Both the fresh build and final-source rebuild succeeded, and the final rebuild reused dependency layers. The runtime passes `pip check`, runs as UID 1000, and contains the built UI with no Azure speech SDK, config fields or token API. Saved credentials are excluded from the image. Logs: `docker-azure-removal-build.log`, `docker-azure-removal-final-build.log` and `docker-azure-removal-image-check.json` under `artifacts/verification/`.

The real Compose `app` and `db` are healthy. Port 8000 serves the new UI, and existing PostgreSQL sessions are preserved. All four saved inference connections were transferred to the new `app-data` volume and verified before/after container restart. Keys remain redacted in API responses and the settings file remains `0600` under UID 1000. Current provider discovery/health succeeds for Agent, ASR, embeddings and reranking. This verifies connectivity, not transcription or model quality. Evidence: `artifacts/verification/docker-compose-updated-runtime.json`.

A separate container from the final image used isolated SQLite and demo inference, with no host source or private settings mounted. Both languages passed creation without a storage-consent field, pause/resume, three answers, reports with STAR/citations, history and deletion; a paused session survived restart. Its temporary container and volume were removed. Evidence: `artifacts/verification/docker-updated-app-smoke.json`.

The actual Docker-served UI was visually inspected at 1440px and 390px. Desktop/mobile axe checks returned no violations, no page errors occurred, and mobile content had no horizontal overflow. The screenshot panel and requested slogans are absent. Evidence: `artifacts/verification/final-ui.json`, `setup.png`, `setup-ready.png` and `setup-mobile.png`. Historical checks below remain dated November 2.

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

The current validated-buffer approach waits for a complete model turn before sending display chunks. Do not claim the four-second first-token or eight-second speech-end-to-audio target has passed. Avatar FPS, speech interruption and final-machine latency remain to be measured.

## Honest scope of the delivered materials

The 1,500 curriculum examples are synthetic drafts: 900 English, 450 Cantonese and 150 mixed-language examples, across the prescribed task proportions. They have **zero completed human reviews**. Template similarities deliberately block promotion until examples are rewritten and reviewed. Training on these drafts is not an authorized shortcut around the review gates.

No adapter, training log, loss curve, base-versus-LoRA preference result or participant study has been invented. GPU scripts and evaluated metric implementations prepare that work; they do not substitute for it. Two team identities and the proposed responsibility table are present, with two placeholders and actual contribution evidence still required.

The current portrait-textured 3D surface supersedes the original procedural avatar and planned VRM asset. Evaluation runs are stored as JSON artifacts rather than database entities. True upstream model-token streaming is pending. The presentation and source package disclose these implementation limits.
