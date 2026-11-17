# VoxPrep HK progress

## Executive summary

The local application, base-model inference, retrieval, speech fallback, training/evaluation tooling and presentation materials are implemented. The Docker app and PostgreSQL run at `http://localhost:4431`; all four saved inference connections are preserved in the Docker volume. Native model launchers remain available for development. The integration branch carries Kelvin's Kaggle v5 training records and automated results. The adapter weights are distributed separately, and participant studies remain pending. Inference providers can now be configured in Settings.

Updated: **2026-11-18T04:42:08+08:00**. See [verification](docs/VERIFICATION.md), [release gates](docs/RELEASE_CHECKLIST.md) and [external setup](docs/EXTERNAL_SETUP.md).

## Working state

- The app uses port **4431** for Docker and native API serving. Jamie is the only included face. Setup previews the appearance before starting, then saves it with the session. A portrait-textured 3D facial surface blinks, moves subtly and animates the mouth during local question playback.
- Starting immediately shows an indeterminate loading bar, actual preparation stages and elapsed time. Duplicate starts are blocked, errors preserve inputs, and late completion cannot redirect another page.
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
- `make package` writes `artifacts/VoxPrep-HK-source.zip` and its SHA-256. Archive integrity and every manifest entry have been verified. Its manifest states whether a verified trained adapter is present. The source archive includes historical evidence and requires a separately verified local adapter to include weights.

## Immediate next targets

1. Follow [external setup](docs/EXTERNAL_SETUP.md) to validate the selected inference services and configure a Colab/Kaggle GPU. Keep credentials in the ignored local `.env` or notebook secret store.
2. Rewrite and human-review the dataset, remove near duplicates, complete first reviews and the stratified second-review sample, then produce leakage-safe splits. The draft count is not a count of curated examples.
3. Run genuine GPU training, retain the best adapter, loss curves, hashes and logs, export a merged GGUF and compare it with the retained base model.
4. Address generation latency and execute the reviewed model/retrieval experiment, four-speaker speech study, avatar performance check and five-to-eight-person usability study. Record failures as well as successes.
5. Rehearse the final seven-minute presentation on the classroom Mac and replace the backup with a recording of the final assessed configuration.

## Last verification

On **2026-11-18**, the latest checks passed **156 Python tests, 70 frontend tests and nine browser journeys**, with one optional PostgreSQL test skipped in the ordinary Python suite. Lint, type checks and the production build passed. Browser coverage includes Jamie-only preselection, saved appearance after reload, delayed startup progress, duplicate-submit prevention, real WebGL canvas loading, controlled speech-start/pause/stop behavior, both interview languages, History and accessibility. Headless speech uses controlled browser events; this is not an audible speech-quality benchmark.

The final Docker image is running at **http://localhost:4431**, with both containers healthy. Migration `0003` preserved all three existing sessions and defaulted them to Jamie. The four inference configurations retained the exact private-file hash and owner-only permissions. Served PNG/mesh hashes match the project assets. Runtime `pip check` passes.

The 3D screenshot and loading screen were visually inspected. The final image also passed isolated desktop, 390px and 320px checks: moving speech frames, static pause/reduced-motion frames, resize recovery, no overflow or page errors, and six axe scans with no violations. The geometry tests verify a continuous portrait boundary, mouth aperture, finite depth, blink/lip deformation and reset. Renderer tests cover hide/show, late initialization, reduced motion and failure cleanup. The source image is unchanged. See [verification](docs/VERIFICATION.md) for Docker deployment evidence and [mesh provenance](docs/INTERVIEWER_PORTRAITS.md) for regeneration and known limits.

## Durable decisions and limits

- Local, single-user classroom use; authentication and public hosting are out of scope. Do not expose the API publicly.
- A base Qwen checkpoint is used while training is pending. Deterministic and heuristic fallbacks are disclosed in the interface and reports.
- Only Jamie is included, per the user’s latest direction. The frontal 3D surface is reconstructed from the fictional portrait; it is not a complete head scan. Speech-driven motion is approximate, not phoneme-perfect lip sync. A static portrait remains the WebGL fallback. Local voice availability depends on the browser and OS.
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

- **2026-11-18:** Replaced the primitive 3D avatar with Alex, Jamie and Sam portrait choices, including the user-requested revised female appearances. Removed Three.js and simulated mouth motion, retained local speech playback, and moved Docker/native public access to port 4431. The new Docker image is running with all settings and sessions preserved. Current asset details are in [portrait provenance](docs/INTERVIEWER_PORTRAITS.md).

- **2026-11-18:** Kept Jamie only, moved appearance to setup and persisted it per session with migration `0003`. Added a precomputed 3D portrait mesh, cancellable automatic question reading, speech-driven mouth cues, reduced-motion/static fallback and immediate startup progress with real stages and elapsed time.
