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

## Colab or Kaggle

1. Rewrite and review the draft dataset following [DATASET.md](DATASET.md). Every example needs real review; selected examples need a second independent reviewer. Resolve duplicates and preserve source and template groups.
2. Produce the reviewed split files and manifest, then run the dataset validation command. Do not disable the gate to manufacture a successful training run.
3. Upload the repository source and reviewed data to your own Colab/Kaggle notebook environment, open the notebook in `ml/`, and select a CUDA GPU. Google documents that [free Colab compute is available but not guaranteed](https://research.google.com/colaboratory/faq.html). Use Kaggle as the planned fallback if necessary.
4. Install the pinned `ml/requirements-train.txt` environment and run the notebook's validation cells before training. The workflow requires a CUDA GPU and does not train on the presentation Mac.
5. Retain the best adapter, configuration, environment record, raw training log, split hashes, loss curve and model manifest. Export and checksum the merged GGUF according to [MODEL_CARD.md](MODEL_CARD.md).
6. Bring the adapter/evidence back under `ml/runs/voxprep-qlora/` and configure the merged local model. `make package` includes only a valid manifest-verified small adapter and approved evidence. It excludes base weights.
7. Run held-out base+RAG, LoRA-only and LoRA+RAG evaluation, blinded ratings and the release checklist before presenting fine-tuning as completed.

## Team details

The README records YUEN Yiu Yeung (23000594D) and SO Ngai Chun (26131699D). Two rows remain intentionally blank for the other members. Proposed subsystem assignments are not claims of actual student contribution; update the contribution log with completed work and review evidence.
