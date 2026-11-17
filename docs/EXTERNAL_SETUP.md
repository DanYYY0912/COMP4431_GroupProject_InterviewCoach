# Azure Speech and GPU training setup

## Executive summary

Azure Speech and a Colab/Kaggle GPU are not set up for this team as of 2 November 2026. The app works locally with Qwen, Whisper, system voice and typed input. The Azure integration and QLoRA workflow are implemented, but genuine service validation and training need accounts, consented recordings, reviewed data and available compute. No paid service or training job has been provisioned. Add the remaining two team identities in the README when available.

## Azure Speech

1. Follow Microsoft's [Speech quickstart](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/get-started-text-to-speech) to create a Speech resource using your own Azure account. Select the intended free tier if offered in the resource creation flow, and check its displayed quota before enabling it.
2. Retrieve the resource key and region from the Azure portal. Put them in the ignored local `.env` file as `AZURE_SPEECH_KEY` and `AZURE_SPEECH_REGION`. Do not put them in the repository, presentation, chat, or training notebook.
3. Restart `make demo`. Health should report Azure configured. Enable Azure voice in setup only after reading the audio/text disclosure.
4. Test recognition and synthesis in both `en-HK` and `zh-HK`. Verify the selected voices against Microsoft's [language and voice support table](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/language-support?tabs=text-to-speech).
5. Check microphone denial, token expiration, service interruption, edited transcripts and pause during playback. Confirm both sound and mouth movement stop.
6. Collect the planned balanced 24 recordings from four consenting speakers. Preserve failures and correction counts for evaluation. Synthetic system speech smoke clips are not replacements for participant data.

The backend exchanges the key for a temporary token. The browser never receives the subscription key. Missing credentials leave typed and local transcription available.

## Kaggle first; Colab fallback

1. Generate WS2's runtime-aligned corpus and complete the human CLI review/merge workflow in [DATASET.md](DATASET.md). Retain real names, UTC timestamps, exact content hashes, independent second reviews and accurate source/story groups. The 1,500 legacy drafts cannot be promoted unchanged. `ml/config.json` currently expects **480**, the planned WS2 count; confirm the actual generated/reviewed count before training. If the team intentionally uses a smaller subset, commit its actual count and explain the experiment.
2. Commit only `ml/data/reviewed_examples.jsonl` plus review evidence/edits to a public fork branch containing WS1, WS2, WS3 and WS5. `ml/.gitignore` excludes generated `data/reviewed/` splits and `runs/`, and **does not** exclude the reviewed source or human review logs. Do not commit personal transcripts, tokens, weights or database files.
3. Complete Kaggle phone verification before enabling Internet/GPU access. In [Kaggle notebook Session options](https://www.kaggle.com/docs/notebooks), turn Internet on and select a CUDA GPU. Qwen3-4B weights download roughly 8 GB; also allow room for package caches, checkpoints and export intermediates. Inspect available disk and the account's displayed GPU quota. The notebook uses one GPU, even on a two-T4 allocation. A T4 lacks BF16: `train.py` automatically selects FP16; other capable GPUs use BF16.
4. Import `ml/VoxPrep_QLoRA.ipynb`, set its `BRANCH` to the published training branch, and run cells in order. The first code cell clones `https://github.com/kelvin0611/COMP4431_GroupProject_InterviewCoach.git` at that branch (default `main`); no manual source/data upload is required. It records the exact commit and stops if the real reviewed corpus is absent. Existing checkouts are not overwritten or automatically pulled.
5. Install pinned dependencies, validate human review and duplicates, then split **inside the notebook** with seed 42. `ml.train --validate-only` verifies the configured count, hashes, schemas, review quota and split isolation before any GPU training. All subprocess calls fail on errors; never bypass these gates. The notebook remains unexecuted in Git and contains no invented logs/results.
6. Train and keep the actual run: adapter, best checkpoint, `loss.png`, `training_log.jsonl`, `model_manifest.json`, split/config/environment and source revision evidence. Resume only from a compatible retained checkpoint using `--resume-from-checkpoint`. The final code cell archives the entire run. Save a Kaggle notebook version with outputs, then download the ZIP; for route B also download the final Q4_K_M GGUF (roughly 2.5 GB, actual size printed). Colab triggers the ZIP download and displays the GGUF link.
7. Export on Kaggle using route B by default. Route A commands and `LORA_PATH` support are available, but the project's real adapter/base inference parity has not been verified; see the diagnostic preflight in [MODEL_CARD.md](MODEL_CARD.md). The notebook records the llama.cpp commit so subsequent conversions can pin it. Only after the final checksum succeeds does it remove its own disposable FP16/merged intermediates to reduce notebook output size.
8. Extract the run ZIP into `ml/runs/voxprep-qlora/` and place the final GGUF under ignored `models/`. Set `MODEL_PROVIDER=llama` and `MODEL_PATH=models/voxprep-Q4_K_M.gguf` in the local `.env`; leave `LORA_PATH` unset for route B. Stop any previous model service yourself before relaunching `make dev` / `make demo`; the launcher never kills services it did not start.
9. Run `python -m evaluation.metadata` to refresh saved Methodology metadata, preserving existing measured evaluations. The local Methodology API also reads the real run manifest on every request. A missing/incomplete manifest keeps `not_trained`; a completed manifest reports `training_completed`, with adapter presence tracked separately. No model-quality result is implied. Run WS4's whole held-out test split comparison and independent ratings before presenting improvement claims. `make package` still verifies adapter manifest hashes and excludes base weights.

If Kaggle compute is unavailable, use a free Colab CUDA runtime with the same notebook; it detects `/content`. Google states that [free compute is not guaranteed](https://research.google.com/colaboratory/faq.html). No GPU runtime, training, conversion or export parity has been executed in this development session.

### Optional Kaggle MCP connection

Kaggle publishes an [official remote MCP server](https://www.kaggle.com/docs/mcp.md) at `https://www.kaggle.com/mcp`. Add it as an HTTP server named `kaggle` in the MCP client's settings and complete its OAuth flow. Do not paste API tokens into chats, the notebook or Git. This is optional: the public-repository clone workflow does not need MCP or an API token. No connection is claimed until the client actually exposes Kaggle tools after authorization.

## Team details

The README records YUEN Yiu Yeung (23000594D) and SO Ngai Chun (26131699D). Two rows remain intentionally blank for the other members. Proposed subsystem assignments are not claims of actual student contribution; update the contribution log with completed work and review evidence.
