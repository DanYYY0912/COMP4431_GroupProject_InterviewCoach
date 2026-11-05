# VoxPrep HK progress

## Executive summary

The local application, base-model inference, retrieval, speech fallback, training/evaluation tooling and presentation materials are implemented. The app runs at `http://localhost:8000` with native Qwen, Whisper, embedding and reranking services and PostgreSQL. This is a working development submission, not a completed assessed release: Azure and a training GPU are not set up, the 1,500 synthetic drafts are unreviewed, and no fine-tuned adapter or participant results exist. Two team identities are filled in; two remain for the team to add.

Updated: **2026-11-02T14:43:03+08:00 (Asia/Hong_Kong)**. See [verification](docs/VERIFICATION.md), [release gates](docs/RELEASE_CHECKLIST.md) and [external setup](docs/EXTERNAL_SETUP.md).

## Working state

- `make demo` builds the frontend, migrates the database and starts the local production interface. `make dev` starts the development interface on port 5173.
- Real local services use ports 8080–8083; Docker PostgreSQL uses loopback port 54329. Model weights are downloaded and checksum-verified on this Mac and excluded from source packaging.
- English and Cantonese typed interviews, adaptive follow-ups, saved state, report, retry, full transcript export, session comparison and deletion have browser coverage. Microphone permission and stale-response races have regression tests.
- Azure recognition, synthesis and viseme integration is implemented but real Azure calls remain unverified. Local Whisper was exercised with synthetic English and Cantonese speech.
- QLoRA scripts, a GPU notebook, review/split gates, export tooling and evaluation runners are present. They deliberately reject unreviewed or leaking training data.
- The eight-slide [PowerPoint](presentation/VoxPrep-HK.pptx), speaker notes, [seven-minute script](presentation/DEMO_SCRIPT.md) and [80-second scripted backup](presentation/backup-demo.mp4) are prepared. The backup uses the deterministic demo provider and fictional answers.
- `make package` writes `artifacts/VoxPrep-HK-source.zip` and its SHA-256. Archive integrity and every manifest entry have been verified. Its manifest states whether a verified trained adapter is present. No adapter currently exists.

## Immediate next targets

1. Follow [external setup](docs/EXTERNAL_SETUP.md) to configure Azure and a Colab/Kaggle GPU. Keep credentials in the ignored local `.env` or notebook secret store.
2. Rewrite and human-review the dataset, remove near duplicates, complete first reviews and the stratified second-review sample, then produce leakage-safe splits. The draft count is not a count of curated examples.
3. Run genuine GPU training, retain the best adapter, loss curves, hashes and logs, export a merged GGUF and compare it with the retained base model.
4. Address generation latency and execute the reviewed model/retrieval experiment, four-speaker speech study, avatar performance check and five-to-eight-person usability study. Record failures as well as successes.
5. Rehearse the final seven-minute presentation on the classroom Mac and replace the backup with a recording of the final assessed configuration.

## Last verification

On 2026-11-02, final checks passed **61 Python tests, 23 frontend tests and five Playwright journeys**, plus lint, type checks, production and Docker builds. The earlier integrated `make test` passed before the final additions; affected suites were rerun after those additions. Both real Qwen language flows completed with source-ID validation and model-generated reports. Container startup and both-language smoke journeys passed. [Verification](docs/VERIFICATION.md) records scope and evidence. Counts describe controlled software checks; they do not establish model quality or human-study thresholds.

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
