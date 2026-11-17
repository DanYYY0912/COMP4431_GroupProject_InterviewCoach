# Inference services and GPU training setup

## Executive summary

Configure Agent, ASR, Embedding and Reranker in Settings using each service's base URL, API key and model. The app supports typed interviews, recorded answers and locally available browser speech. QLoRA training still needs reviewed data and a Colab/Kaggle GPU; no paid service or training job has been provisioned. Service checks and participant studies must use the final selected providers.

## Inference services

1. Enter the service's API base URL, key if required, and model in its Settings section. Use **Load models** if discovery is supported; otherwise enter the model ID.
2. Save the configuration. See the endpoint formats and credential handling in the [README](../README.md#configuration-and-real-services).
3. From Docker, use `host.docker.internal` to reach inference servers on your Mac. `localhost` inside the application container refers to the container itself.
4. Check English and Cantonese transcription, microphone denial, unavailable services, editable transcripts and playback interruption with your selected configuration. Browser speech requires a compatible local voice.
5. Collect the balanced 24 recordings from four consenting speakers for evaluation. Preserve failures and correction counts; synthetic system speech clips are not participant evidence.

## Colab or Kaggle

1. Rewrite and review the draft dataset following [DATASET.md](DATASET.md). Every example needs real review; selected examples need a second independent reviewer. Resolve duplicates and preserve source and template groups.
2. Produce the reviewed split files and manifest, then run the dataset validation command. Do not disable the gate to manufacture a successful training run.
3. Upload the repository source and reviewed data to your own Colab/Kaggle notebook environment, open the notebook in `ml/`, and select a CUDA GPU. Google documents that [free Colab compute is available but not guaranteed](https://research.google.com/colaboratory/faq.html). Use Kaggle as the planned fallback if necessary.
4. Install the pinned `ml/requirements-train.txt` environment and run the notebook's validation cells before training. The workflow requires a CUDA GPU and does not train on the presentation Mac.
5. Retain the best adapter, configuration, environment record, raw training log, split hashes, loss curve and model manifest. Export and checksum the merged GGUF according to [MODEL_CARD.md](MODEL_CARD.md).
6. Bring the adapter/evidence back under `ml/runs/voxprep-qlora/` and configure the merged local model. `make package` includes only a valid manifest-verified small adapter and approved evidence. It excludes base weights.
7. Run held-out base+RAG, LoRA-only and LoRA+RAG evaluation, blinded ratings and the release checklist before presenting fine-tuning as completed.

## Team details

The README records the current team identities. Proposed subsystem assignments are not claims of actual student contribution; update the contribution log with completed work and review evidence.
