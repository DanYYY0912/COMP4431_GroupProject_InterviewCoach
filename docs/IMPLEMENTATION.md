# Implementation checkpoints

## Executive summary

Build the supplied VoxPrep HK plan from the two course PDFs in this folder. The initial repository is empty. Work is split across the API, interface, training/evaluation tooling, and integration. Offline demonstration behavior must remain visibly distinct from real model inference. Training, human review, service credentials, and participant testing require real external inputs before the assessed release can be declared complete.

## Ordered work

1. Freeze shared contracts; establish Python API and React tooling. Verify imports, schema tests, and production build.
2. Complete ingestion → bilingual typed interview → report → history/export/delete. Verify API integration and browser journeys.
3. Connect local inference, retrieval, speech, and avatar with recoverable fallbacks. Verify deterministic service failures and real available services.
4. Prepare dataset review, QLoRA, export and evaluation workflows. Verify fixtures and reject unreviewed training inputs; never invent training/evaluation results.
5. Add reproducible commands, CI, documentation, presentation and source archive. Verify package contents and a complete clean-browser demonstration.

## Ownership

- Backend agent: `backend/`, `knowledge/`.
- Frontend agent: `frontend/`.
- Model agent: `ml/`, `evaluation/`, model/data documentation.
- Integration agent: root scripts, infrastructure, contracts, presentation and end-to-end verification.

## External release gates

- 1,500 reviewed examples and required second reviews; genuine GPU QLoRA training and retained artifacts.
- Azure Speech configuration and recordings from four speakers.
- Blinded model ratings, five to eight usability participants and measured release thresholds.
- Four team member names/IDs, live rehearsal and final backup recording.
