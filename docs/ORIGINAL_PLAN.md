# VoxPrep HK — Hardcore Bilingual AI Interview Coach

## Executive summary

This document proposes a complete, local-first COMP4431 chatbot project optimized for the grading criteria; it is a plan, not an implemented or tested system. VoxPrep HK will help Hong Kong technology graduates practise English or Cantonese interviews by importing a job description, conducting an adaptive voice interview through a lip-synced 3D avatar, and producing evidence-linked STAR coaching. A genuinely QLoRA-fine-tuned 4B language model will run locally on the presentation Mac, while retrieval, Azure Speech, and measured fallbacks provide grounded answers and a reliable live demonstration. The submission package will include source code, training evidence, evaluations, documentation, slides, a rehearsed seven-minute demo, and a backup recording. Public hosting, authentication, hiring decisions, emotion analysis, and protected-trait scoring are deliberately out of scope.

## 1. Project outcome

Build a local-first web application for Hong Kong university students preparing for software, data, and AI graduate interviews. The complete experience will:

- Import a job description and derive role-specific competencies.
- Conduct an adaptive English or Cantonese voice interview through a lip-synced 3D interviewer.
- Use a genuinely QLoRA-fine-tuned bilingual LLM, not prompt engineering presented as fine-tuning.
- Ground questions and feedback in the job description, a competency library, and a STAR-response rubric.
- Produce evidence-linked coaching, speech analytics, retry exercises, history, and an exportable report.
- Include visible methodology and evaluation results so assessors can verify the technical contribution.

“Hardcore” is a user-selected ambition level rather than an official course tier. It means implementing all four listed additions—voice recognition and synthesis, a 3D avatar, a fine-tuned LLM, and a polished interface—plus retrieval-augmented generation (RAG), adaptive interviewing, measurable evaluation, accessibility, privacy, and failure recovery.

### Source requirements

- Feature brief: `/Users/dannyyuen/Downloads/COMP4431_GroupProjectRequirement.pdf`
- Full course specification: `/Users/dannyyuen/Downloads/COMP4431_GroupProject2027.pdf`
- Team: four students.
- Delivery: complete runnable submission package and presentation materials.
- Presentation: seven-minute English presentation and live demonstration, followed by Q&A.

## 2. Product and technical design

### User experience

1. **Dashboard:** Start or resume practice, review history, and inspect methodology and model results.
2. **Interview setup:** Paste or upload a text-based PDF, DOCX, or TXT job description up to 5 MB; choose English or Cantonese, difficulty, and 3, 5, or 8 questions; run microphone, speaker, and model preflight; and confirm transcript storage.
3. **Live interview:** Show the 3D interviewer, live editable captions, waveform, timer, question progress, listening/thinking/speaking states, and pause, repeat, re-record, skip, and text-fallback controls.
4. **Adaptive questioning:** Retrieve job competencies and ask follow-ups that target missing STAR elements or unsupported claims.
5. **Debrief:** Show Situation, Task, Action, and Result completeness; competency evidence; strengths; one prioritized improvement; pace, pause, filler-word, and answer-length metrics; citations; and a retry exercise.
6. **History and methodology:** Compare sessions, export or delete data, and expose dataset provenance, training configuration, loss curves, base-versus-LoRA results, retrieval metrics, latency, limitations, and a model card.

The application will not perform emotion, appearance, accent-quality, personality, protected-trait, employability, candidate-ranking, or hiring-decision scoring.

### Application stack

- **Frontend:** React 19, TypeScript, Vite, Tailwind CSS, React Three Fiber 9, Three.js, and `@pixiv/three-vrm`.
- **Backend:** Python 3.12, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, and strict JSON-schema validation.
- **Storage:** PostgreSQL 17 with pgvector. Store job profiles, source chunks, sessions, turns, evidence, speech metrics, and evaluation runs.
- **LLM:** `Qwen/Qwen3-4B-Instruct-2507`, selected for its 4B footprint, bilingual capability, Apache-2.0 license, and local-serving support.
- **Inference:** Merge the final adapter, export Q4_K_M GGUF, and run native `llama-server` with Apple Metal outside Docker. Retain the base model separately for offline A/B evaluation.
- **Retrieval:** `Qwen3-Embedding-0.6B`, PostgreSQL full-text search, HNSW vector search, reciprocal-rank fusion, and `Qwen3-Reranker-0.6B`. Rerank 12 candidates and send the top four cited passages to the LLM.
- **Knowledge:** The uploaded job description, a locally authored STAR rubric, and attributed O*NET 31.0 skills, tasks, and work-activities data for selected technology occupations.
- **Speech:** Azure Speech F0 for `en-HK` and `zh-HK` recognition, neural text-to-speech, and timed viseme IDs.
- **Fallbacks:** Native `whisper.cpp` for local speech-to-text, browser or system speech or text-only output when cloud synthesis fails, amplitude-based mouth movement when timed visemes are unavailable, and a static portrait when WebGL fails.
- **Packaging:** Docker Compose runs PostgreSQL and application services. Native llama.cpp and whisper.cpp retain Apple Metal acceleration. The production frontend is served through one localhost endpoint.

### Authoritative implementation references

- [Qwen3-4B-Instruct-2507 model card](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507)
- [Qwen QLoRA and Unsloth guide](https://qwen.readthedocs.io/en/latest/training/unsloth.html)
- [Qwen llama.cpp guide](https://github.com/QwenLM/Qwen3/blob/main/docs/source/run_locally/llama.cpp.md)
- [Qwen3 Embedding and reranking](https://qwenlm.github.io/blog/qwen3-embedding/)
- [pgvector](https://github.com/pgvector/pgvector)
- [Azure Speech language and voice support](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=text-to-speech)
- [Azure Speech viseme workflow](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/how-to-speech-synthesis-viseme)
- [Azure Speech pricing and free limits](https://azure.microsoft.com/en-us/pricing/details/speech/)
- [React Three Fiber compatibility](https://r3f.docs.pmnd.rs/getting-started/installation)
- [three-vrm](https://github.com/pixiv/three-vrm)
- [O*NET 31.0 database](https://www.onetcenter.org/database.html)
- [O*NET database license](https://www.onetcenter.org/license_db.html)

### Fine-tuning specification

- Create 1,500 human-reviewed instruction examples:
  - 60% English, 30% Traditional-Chinese Cantonese, and 10% code-switching.
  - 40% interview questions and adaptive follow-ups, 35% STAR feedback, 15% structured reports, and 10% safety and language-boundary cases.
- Split the dataset 80/10/10 by role family and job-description source, preventing template or near-duplicate leakage.
- Require one human review for every example and a second review for a stratified 15% sample.
- Train in free Google Colab first and Kaggle second; do not train on the demonstration Mac.
- Use the following QLoRA configuration:
  - 4-bit NF4 with double quantization.
  - LoRA rank 32, alpha 64, dropout 0.05, and all linear layers targeted.
  - 2,048-token sequences, effective batch 32, learning rate `2e-4`, cosine decay, 5% warm-up, three epochs, seed 42, gradient checkpointing, and assistant-only loss.
  - BF16 when the GPU supports it and FP16 otherwise.
  - Preserve the checkpoint with the best validation loss.
- Retain dataset hashes, provenance, configurations, logs, loss curves, adapter checkpoints, the final adapter, model manifest, and raw evaluation results.

### Retrieval specification

- Validate file type, file size, and extracted text before ingestion.
- Reject scanned or image-only documents with a clear instruction to paste the text; OCR is out of scope.
- Treat every uploaded document as untrusted quoted data, never as system instructions.
- Chunk sources at approximately 450 tokens with an 80-token overlap and retain source metadata.
- Perform full-text and vector retrieval, fuse rankings, rerank the top 12 chunks, and provide the four strongest passages to the LLM.
- Require every factual job or competency claim in feedback to reference a retrieved source chunk.

## 3. Interfaces and contracts

### HTTP interfaces

- `POST /api/job-profiles` — Accept pasted text or one validated file; return a normalized role, competencies, source warnings, and profile ID.
- `POST /api/sessions` — Create a five-question default session from a job profile, language, and difficulty.
- `GET /api/sessions` — Return local session history.
- `GET /api/sessions/{id}` — Return resumable interview state.
- `GET /api/sessions/{id}/report` — Return the evidence-linked debrief and speech metrics.
- `DELETE /api/sessions/{id}` — Permanently remove the local session data.
- `POST /api/speech/token` — Exchange the server-held Azure secret for a short-lived browser token; never expose the subscription key.
- `POST /api/speech/transcribe` — Transcribe recorded audio through the local Whisper fallback.
- `GET /api/methodology/metrics` — Return stored evaluation results for the methodology screen.
- `GET /api/health` — Report readiness for the database, LLM, speech, and retrieval components.

### Real-time interface

`WS /api/sessions/{id}/live` will carry:

- Transcript submissions and corrected transcripts.
- Pause, cancel, retry, skip, and end controls.
- Streaming model text deltas.
- Interview-state transitions.
- Final schema-validated interviewer turns.
- Recoverable error and fallback messages.

### Shared types

- `LanguageMode = "en-HK" | "zh-HK"`
- `InterviewState = setup | ready | listening | transcribing | thinking | speaking | paused | completed | error`
- `AnswerSubmission` contains transcript, language, elapsed time, correction flag, and client speech metrics.
- `CoachTurn` contains interviewer text, question type, targeted competencies, adaptive-follow-up reason, and source citations.
- `SessionReport` contains STAR evidence, competency feedback, speech metrics, prioritized improvement, retry exercise, citations, and limitations.
- Socket messages use a versioned discriminated union. Malformed messages and model output fail schema validation before reaching the UI.

### Operator commands

Provide these stable commands:

- `make bootstrap` — Install or download required application and native runtime dependencies.
- `make dev` — Start the development database, API, frontend, and model services.
- `make test` — Run unit, integration, contract, accessibility, and end-to-end tests.
- `make eval` — Run model, RAG, speech, latency, and usability evaluation pipelines.
- `make demo` — Start the production demonstration stack.
- `make demo-reset` — Restore the deterministic demonstration account and scenario.
- `make package` — Build the submission archive while excluding secrets and large base-model weights.

## 4. Implementation sequence

### Days 1–2: Contracts and walking skeleton

- Freeze schemas, routes, event contracts, visual design tokens, data rules, and model prompts.
- Scaffold the frontend, backend, database migrations, Docker Compose, CI, mocks, and one-click health page.
- Establish linting, formatting, type checking, tests, secret handling, and lockfiles.
- **Checkpoint:** A mocked setup → interview → report journey runs end to end.

### Days 3–6: Complete text vertical slice

- Implement job ingestion, the O*NET competency subset, chunking, hybrid retrieval, interview state machine, structured LLM output, citations, report generation, history, export, and deletion.
- Run the base Qwen model locally while the fine-tuning dataset is prepared.
- **Checkpoint:** A five-question typed interview works in English and Cantonese without speech or avatar dependencies.

### Days 4–10: Parallel assessed features

- **Student 1 — Product/UI/3D:** Responsive interface, original or licensed VRM avatar, animation states, viseme mapping, accessibility, and report visualizations.
- **Student 2 — Speech:** Azure recognition and TTS, editable captions, interruption handling, local STT fallback, speech analytics, and speech benchmarks.
- **Student 3 — Model/evaluation:** Dataset curation, QLoRA notebook, model export, base-versus-LoRA benchmark, model card, and result charts.
- **Student 4 — Backend/RAG/reliability:** Job ingestion, retrieval, interview orchestration, persistence, schemas, observability, prompt-injection defenses, Docker automation, and recovery paths.
- Every student cross-reviews another subsystem. Shared contracts change only through documented team agreement.

### Days 10–12: Integration and feature freeze

- Connect fine-tuned inference, retrieval, speech, timed visemes, report generation, cancellation, and fallback state transitions.
- Add the methodology screen, telemetry, seeded scenario, and deterministic demo reset.
- Resolve integration bugs and freeze new feature work after the complete flow passes.
- **Checkpoint:** The primary scenario and every major fallback work on the M4 presentation Mac.

### Days 13–14: Evaluation and polish

- Execute model, RAG, speech, latency, accessibility, robustness, and usability evaluations.
- Fix high-impact defects and update methodology evidence from final results.
- Conduct peer usability testing and a clean-browser rehearsal.

### Days 15–16: Submission and presentation

- Produce the README, architecture diagram, model card, evaluation report, data-source/license manifest, contribution matrix, slides, speaker notes, demo script, and known-limitations section.
- Record a 60–90 second backup demonstration.
- Run `make package`, verify archive contents and checksums, and rehearse the seven-minute presentation on the final machine.

## 5. Verification and release gates

### Functional requirements

- Complete setup, interview, debrief, retry, history, export, and deletion in English and Cantonese.
- Preserve the complete experience through typed input when microphone or speech services are unavailable.
- Show relevant, role-specific questions and feedback for the selected technology domain.
- Keep citations attached to the exact feedback claims they support.

### Model evaluation

- Evaluate 120 held-out prompts covering both languages and every trained task.
- Compare base+RAG, LoRA-only, and LoRA+RAG under identical prompts and decoding settings.
- Achieve at least 98% structured-schema validity.
- Achieve at least 95% requested-language adherence.
- Achieve at least 65% blinded preference for LoRA+RAG over base+RAG on 30 paired examples rated by two reviewers.
- Report inter-rater agreement, training and validation loss, failures, and representative examples.

### Retrieval evaluation

- Use 40 questions with known supporting passages.
- Target recall@5 of at least 85%.
- Target citation precision of at least 90%.
- Record unsupported-claim and prompt-injection failure rates.

### Speech and avatar evaluation

- Test 24 clean and noisy recordings from at least four speakers, balanced across English and Cantonese.
- Report English word error rate, Cantonese character error rate, transcript correction rate, and failures without cherry-picking.
- Require correct listening, thinking, and speaking states for every scripted test.
- Require audio and visemes to stop together when interrupted.
- Maintain at least 30 FPS for the avatar on the presentation Mac.

### Performance and UX evaluation

- Target p95 local first-token latency of no more than four seconds.
- Target p95 speech-end-to-first-audio latency of no more than eight seconds.
- Run five to eight peer usability tests.
- Target at least 90% completion of setup → interview → review.
- Target a System Usability Scale score of at least 80.
- Meet WCAG AA contrast, keyboard-navigation, visible-focus, caption, and reduced-motion requirements.
- Permit users to disable the avatar without losing voice, captions, or interview functionality.

### Robustness scenarios

Test and document recovery from:

- Denied microphone permission.
- Silence, excessive answer length, background noise, and wrong language selection.
- Azure outage, network loss, or expired speech token.
- WebGL failure or poor graphics performance.
- User interruption during TTS playback.
- Corrupt, oversized, scanned, or unsupported documents.
- Prompt injection embedded in a job description.
- Malformed model JSON or model timeout.
- Database or local model restart.

### Automated test stack

- pytest for backend behavior and model contracts.
- Vitest and Testing Library for frontend components and state transitions.
- Playwright for complete browser journeys.
- axe for automated accessibility checks.
- Golden-schema tests for training examples, evaluation fixtures, and model output.
- Stubbed Azure/model tests for deterministic CI plus manual tests against real services before release.

## 6. Presentation and submission package

### Seven-minute presentation

- **0:00–0:30 — Problem:** Generic interview tools ignore the actual job and provide weak support for Hong Kong bilingual candidates.
- **0:30–1:00 — Contribution:** Show one architecture slide covering genuine fine-tuning, RAG, voice, 3D lip-sync, analytics, and privacy.
- **1:00–1:30 — Setup:** Import a prevalidated technology-intern job description and select English or Cantonese.
- **1:30–3:40 — Live interview:** Give an intentionally incomplete answer and show captions, avatar states, lip-sync, and an adaptive follow-up targeting the missing STAR evidence.
- **3:40–4:40 — Debrief:** Show evidence-linked STAR feedback, citations, speech analytics, and the retry exercise.
- **4:40–5:35 — Technical depth:** Explain QLoRA, retrieval isolation, structured validation, viseme timing, and fallbacks.
- **5:35–6:25 — Results:** Present base-versus-LoRA-versus-LoRA+RAG, retrieval, speech, latency, and usability results.
- **6:25–7:00 — Ethics and close:** State limitations and safety boundaries, summarize contributions, and finish with the product value proposition.

Use one rehearsed lead presenter for narrative continuity and assign every student a Q&A specialty.

### Final deliverables

- Complete source repository and lockfiles.
- Docker Compose configuration and one-command demo scripts.
- Database migrations and seeded demonstration scenario.
- Fine-tuning notebook, dataset, provenance, hashes, configuration, logs, loss curves, adapter, and model manifest.
- Evaluation scripts, raw results, charts, and model card.
- Knowledge-base files, prompts, and source/license attribution.
- README with setup, run, troubleshooting, architecture, features, and limitations.
- Presentation deck, speaker notes, timed demo script, contribution matrix, and Q&A preparation.
- Backup demonstration recording.
- Submission archive with checksums. Large base-model/GGUF weights remain on the demo Mac; include the small adapter, manifest, checksums, and reproducible download/conversion script instead.

## 7. Locked assumptions and boundaries

- This is a local-first, single-user classroom application; authentication, public hosting, and multi-user collaboration are out of scope.
- The Apple M4 MacBook Air with 24 GB RAM is the presentation target and performs inference only.
- Azure Speech F0 is the primary speech path. Credentials remain server-side.
- English and Cantonese are selected per answer. Same-sentence code-switch transcription is best-effort and always editable, not a guaranteed accuracy claim.
- Google Colab is the primary training environment and Kaggle is the fallback. Development continues with the base model if a notebook GPU is temporarily unavailable.
- Uploaded documents and transcripts remain local except for audio transmitted to Azure Speech after user consent.
- The avatar is original or has documented presentation and redistribution rights.
- The chatbot is a practice coach, never a hiring or candidate-ranking system.
- Implementation is not complete until the full flow, fallbacks, evaluation evidence, clean-machine rehearsal, and submission package pass the stated release gates.
