# VoxPrep HK progress

## Executive summary

The local application, base-model inference, retrieval, speech fallback, training/evaluation tooling and presentation materials are implemented. The Docker app and PostgreSQL run at `http://localhost:8000`; all four saved inference connections are preserved in the Docker volume. Native model launchers remain available for development. This is a working development submission, not a completed assessed release: a training GPU is not set up, the 1,500 synthetic drafts are unreviewed, and no fine-tuned adapter or participant results exist. Inference providers can now be configured in Settings.

Updated: **2026-11-18T03:54:46+08:00 (Asia/Hong_Kong)**. See [verification](docs/VERIFICATION.md), [release gates](docs/RELEASE_CHECKLIST.md) and [external setup](docs/EXTERNAL_SETUP.md).

## Working state

- Practice interview opens directly. The two input sections control start readiness; the right panel summarizes configuration and service status. History preserves session management. Overview, consent controls and decorative marketing copy have been removed.
- The former Methodology tab is now **Settings**, with Agent, ASR, Embedding and Reranker connections. Each accepts a base URL, API key and model; discovery is optional and manual model IDs are supported.
- Provider settings persist server-side with keys redacted from API responses. Saved settings apply to new requests and override environment defaults after restart. Public services require HTTPS; local/private network servers can use HTTP. External providers receive their task inputs.
- Recorded answers use the selected ASR service. Leaving ASR empty retains native Whisper. Different embedding models/dimensions use isolated caches. Docker keeps settings in the `app-data` volume; Git and source archives exclude settings and temporary credential files.

- `make demo` builds the frontend, migrates the database and starts the local production interface. `make dev` starts the development interface on port 5173.
- Native model launchers use ports 8080–8083; Docker PostgreSQL uses loopback port 54329. Model weights are downloaded and checksum-verified on this Mac and excluded from source packaging.
- English and Cantonese typed interviews, adaptive follow-ups, saved state, report, retry, full transcript export, session comparison and deletion have browser coverage. Microphone permission and stale-response races have regression tests.
- Azure integration has been removed. Question playback uses local browser voices, while ASR uses the selected server or native Whisper. Local Whisper was exercised with synthetic English and Cantonese speech.
- QLoRA scripts, a GPU notebook, review/split gates, export tooling and evaluation runners are present. They deliberately reject unreviewed or leaking training data.
- The eight-slide [PowerPoint](presentation/VoxPrep-HK.pptx), speaker notes, [seven-minute script](presentation/DEMO_SCRIPT.md) and [80-second scripted backup](presentation/backup-demo.mp4) are prepared. The backup uses the deterministic demo provider and fictional answers.
- `make package` writes `artifacts/VoxPrep-HK-source.zip` and its SHA-256. Archive integrity and every manifest entry have been verified. Its manifest states whether a verified trained adapter is present. No adapter currently exists.

## Immediate next targets

1. Follow [external setup](docs/EXTERNAL_SETUP.md) to validate the selected inference services and configure a Colab/Kaggle GPU. Keep credentials in the ignored local `.env` or notebook secret store.
2. Rewrite and human-review the dataset, remove near duplicates, complete first reviews and the stratified second-review sample, then produce leakage-safe splits. The draft count is not a count of curated examples.
3. Run genuine GPU training, retain the best adapter, loss curves, hashes and logs, export a merged GGUF and compare it with the retained base model.
4. Address generation latency and execute the reviewed model/retrieval experiment, four-speaker speech study, avatar performance check and five-to-eight-person usability study. Record failures as well as successes.
5. Rehearse the final seven-minute presentation on the classroom Mac and replace the backup with a recording of the final assessed configuration.

## Last verification

On **2026-11-18**, `make test` passed **135 Python tests, 39 frontend tests and seven browser journeys**; the optional PostgreSQL test was skipped in this ordinary suite and passed separately during the earlier settings work. Lint, type checks and the production frontend build passed. The browser suite covers default Practice entry, valid-input gating, read-only configuration status, both languages, history, inference settings and accessibility. Log: `artifacts/verification/azure-removal-full-test.log`.

The Docker dependency timeout is resolved. Both the fresh image build and a subsequent build from final source passed; the latter reused cached dependencies. The actual Compose `app` and `db` are healthy, and the updated UI is served on port 8000. The native supervisor was stopped to free the port. Existing sessions and all four saved inference connections survived the transition and an app restart. Settings retain owner-only permissions under UID 1000, and API responses redact keys. Current health reports the configured Agent, ASR model, hybrid retrieval and reranker available; this is connectivity evidence, not a model-quality result.

An isolated container from the new image completed English/Cantonese typed interviews, reports, history, deletion and pause/resume across restart without binding host source. Actual Docker-served desktop/mobile screenshots passed accessibility checks with no page errors or horizontal overflow. Evidence is in `artifacts/verification/docker-azure-removal-*.log`, `docker-compose-updated-runtime.json`, `docker-updated-app-smoke.json`, `final-ui.json` and `setup*.png`. Historical November 2 evidence remains in [verification](docs/VERIFICATION.md).

## Durable decisions and limits

- Local, single-user classroom use; authentication and public hosting are out of scope. Do not expose the API publicly.
- A base Qwen checkpoint is used while training is pending. Deterministic and heuristic fallbacks are disclosed in the interface and reports.
- The avatar uses original procedural Three.js geometry rather than a VRM asset. It needs no external avatar license or download.
- WebSocket text chunks are emitted after complete model output passes validation. They are not upstream token streaming; first-token and speech-to-audio targets remain unmet/unverified.
- Citation IDs and quoted answer evidence are validated. Correct IDs alone do not establish semantic support, which still needs human evaluation.
- Synthetic diagnostic inputs and raw results may be packaged. User session databases, private transcripts, secrets, base weights and generated audio fixtures are excluded.
- Keep the two original course PDFs intact. They predate the source repository and are not redistributed in the generated archive.

## Milestones

- **2026-11-02:** Read the supplied plan and both course PDFs; initialized source control and contracts. Built API, interface, local services, original avatar, data-review/training tooling and evaluation runners.
- **2026-11-02:** Fixed migration adoption, nullable answer contracts, accessibility contrast/labels, Cantonese citation generation, microphone cancellation and stale session responses. Prepared validated slides, scripted backup and source packaging.
- **2026-11-02:** User confirmed Azure and GPU are not configured; supplied two team identities and asked implementation to continue. External evidence gates remain explicit.

- **2026-11-18:** Replaced Methodology with four inference settings sections, integrated authenticated provider calls and runtime persistence, tested dimension-safe retrieval, and updated launch, Docker and source-packaging behavior. Existing slides and backup recording retain their original November 2 presentation snapshot.

- **2026-11-18:** Removed Azure SDK, token exchange, credentials and cloud-voice controls. Replaced setup consent/preflight with a read-only configuration summary and direct Practice interview entry. Repaired Docker dependency downloads, built the final image and launched app/database in Docker Desktop; preserved and restart-verified user settings and sessions.
