# VoxPrep HK progress

## Executive summary

The local application, base-model inference, retrieval, speech fallback, training/evaluation tooling and presentation materials are implemented. The app runs at `http://localhost:8000` with native Qwen, Whisper, embedding and reranking services and PostgreSQL. This is a working development submission, not a completed assessed release: Azure is unverified, the 1,000 runtime-aligned drafts are unreviewed, and no fine-tuned adapter or participant results exist. Two team identities are filled in; two remain for the team to add.

Updated: **2026-11-16T14:30:00+00:00**. See [verification](docs/VERIFICATION.md), [release gates](docs/RELEASE_CHECKLIST.md) and [external setup](docs/EXTERNAL_SETUP.md).

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
2. Human-review `ml/data/runtime_drafts.jsonl` (1,000 runtime-aligned rows, 151 assigned a second review), then produce leakage-safe splits. The draft count is not a count of curated examples.
3. Run genuine GPU training, retain the best adapter, loss curves, hashes and logs, export a merged GGUF and compare it with the retained base model.
4. Address generation latency and execute the reviewed model/retrieval experiment, four-speaker speech study, avatar performance check and five-to-eight-person usability study. Record failures as well as successes.
5. Rehearse the final seven-minute presentation on the classroom Mac and replace the backup with a recording of the final assessed configuration.

## Last verification

On 2026-11-02, final checks passed **61 Python tests, 23 frontend tests and five Playwright journeys**, plus lint, type checks, production and Docker builds. The earlier integrated `make test` passed before the final additions; affected suites were rerun after those additions. Both real Qwen language flows completed with source-ID validation and model-generated reports. Container startup and both-language smoke journeys passed.

On 2026-11-16, `pytest backend/tests ml/tests evaluation/tests scripts/tests` passed **after the review work** with `ruff check backend ml evaluation scripts` clean. That run covered the WS2 runtime-aligned corpus (1,000 generated rows, zero near-duplicates at 0.90, no row above 2,048 tokens), the prescreen triage tool, and the retrieval-labelling, speech-scoring, SUS, latency, injection and Kaggle-run harnesses.

Human review of that corpus is now complete: **971 rows approved, 29 rejected** (the pre-screen-flagged rows), **148 rows with an independent second review**, and `ml.dataset validate --require-review --check-duplicates` returns `valid: true`. The split is 790 train / **62 validation / 119 test** (seed 42, grouped by role family, source and story), so assessed model evaluation reports **119 held-out rows**, not a rounded 120.

One provenance detail belongs here rather than in a slide: the pipeline code was written on Friday 2026-11-13, the reviewer spent **Saturday 2026-11-14 and Sunday 2026-11-15** reading the rows one by one and marking decisions, and those decisions were entered in a single batch pass on **Monday 2026-11-16**. **`reviews[].reviewed_at` is the entry timestamp** (primary `15:13:21Z`–`15:27:39Z`; second reviewer `15:22:51Z`–`15:33:43Z`), so it is two days later than the reading it records. The AI pre-screen notes were hints the reviewer could accept or ignore; the triage tool never writes `reviews`. The original marking artefact with the 29 rejection reasons is kept at `ml/data/evidence/reject_reasons_29.jsonl` — see [DATASET.md](docs/DATASET.md#how-the-corpus-was-actually-reviewed). No training run had been executed at that point.

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
- **2026-11-16:** Shipped WS1 (shared coach prompt builders and output validators in `backend/app/coach.py`), WS3 (`ml/review.py` terminal review tool) and WS5 (training config, Kaggle-first notebook, export path, `scripts/dev.py` `LORA_PATH`) to the fork's `main`.
- **2026-11-16:** Generated the WS2 runtime-aligned corpus: 1,000 rows (450 question / 350 report / 200 safety; 600 en-HK / 400 zh-HK) across 15 Hong Kong role families, 180 stories and 30 fictional job descriptions. Every prompt comes from the app's own builders; zero near-duplicates at 0.90; no row above 2,048 tokens; `reviews` empty on every row.
- **2026-11-16:** Added the measurement harnesses the checklist needs: DeepSeek prescreen triage for drafts, a standard SUS usability scorer, a latency benchmark, and a one-command Kaggle training path. 197 tests pass; ruff clean. Scope note: manual language review of the 119 test outputs, human labelling of a 40-query retrieval set and a WER/CER speech study were dropped, so their harnesses (`scripts/review_retrieval.py`, `scripts/score_speech.py`) exist but are not part of the assessed evidence.
- **2026-11-16:** Kaggle GPU access verified on a private diagnostic kernel (Tesla T4, 14.6 GiB, CUDA available); the stock image's transformers 5.x breaks bitsandbytes, so `ml/requirements-train.txt` pins are required. No training run has been executed.
