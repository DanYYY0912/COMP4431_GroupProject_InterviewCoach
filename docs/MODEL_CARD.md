# VoxPrep HK model card

## Executive summary

Kelvin's recorded Kaggle T4 run fine-tuned Qwen3-4B-Instruct-2507 for one epoch with QLoRA on 971 reviewed examples. Validation loss reached 0.0561. The [training evidence](../ml/training_evidence/voxprep-qlora-v5/) includes the run manifest, loss curve and file hashes. Obtain the matching weights separately to use the trained model.

## Identity and intended use

| Field | Value |
|---|---|
| Base | `Qwen/Qwen3-4B-Instruct-2507` |
| Pinned base revision | `cdbee75f17c01a7cc42f958dc650907174af0554` |
| Base license | Apache-2.0; see the upstream model card |
| Adapter | Recorded in the Kaggle manifest. Weights distributed separately |
| Training status | Kaggle v5 completed 16 November 2026 |
| Evaluated languages | English and Cantonese with an automated script check on 119 examples |
| Intended use | Classroom interview practice for Hong Kong technology graduates |
| Excluded use | Hiring/ranking, employability prediction, protected-trait, emotion, personality or accent-quality scoring |
| Deployment target | Local llama.cpp with Apple Metal; merged Q4_K_M GGUF |

The base model has 4B parameters and a non-thinking instruction interface, according to the [Qwen model card](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507). Upstream benchmark results are not VoxPrep evaluation evidence.

## Training configuration

`ml/config.json` records the proposed experiment and immutable Hugging Face commit hash. The tokenizer, model and export all use that same revision; floating tags such as `main` are rejected. `ml/train.py` uses Transformers 4.57.1, PEFT, and bitsandbytes directly, with an explicit assistant-only token mask. This avoids relying on a model chat template to expose an assistant mask. It checks that the prompt token sequence is an exact prefix of the completed conversation and masks all prompt/padding labels with `-100`.

| Parameter | Setting |
|---|---|
| Quantization | 4-bit NF4, double quantization |
| LoRA | rank 32, alpha 64, dropout 0.05, all linear layers |
| Sequence limit | 2,048 tokens; oversize examples fail rather than silently lose target text |
| Effective batch | 16 on one CUDA GPU: microbatch 1 × 16 accumulation steps |
| Schedule | 1 epoch, learning rate 2e-4, cosine decay, 5% warm-up |
| Precision | BF16 when supported; FP16 otherwise |
| Memory | Gradient checkpointing, paged AdamW 8-bit |
| Selection | Lowest validation loss; evaluation and save every 10 optimizer steps; log every 2 |
| Seed | 42 |
| Reporting | Local logs only; no automatic third-party tracking |

The implementation follows the official [PEFT quantization guide](https://huggingface.co/docs/peft/developer_guides/quantization), [Transformers 4.57.1 Trainer API](https://huggingface.co/docs/transformers/v4.57.1/en/main_classes/trainer), and [chat-template interface](https://huggingface.co/docs/transformers/v4.57.1/en/chat_templating). GPU package versions are pinned in `ml/requirements-train.txt`; the recorded GPU environment is included with the Kaggle evidence.

## Reproduce a training run

Open `ml/VoxPrep_QLoRA.ipynb` with a CUDA GPU and follow the [private Kaggle workflow](KAGGLE_RUN.md). Attach the reviewed corpus privately. The recorded run uses 790 training rows, 62 validation rows, and 119 test rows. T4 uses FP16 and the loader validates the reviewed corpus against the configured count before training.

```sh
python -m pip install -r ml/requirements-train.txt
python -m ml.train --config ml/config.json --validate-only
python -m ml.train --config ml/config.json
```

Keep the entire `ml/runs/voxprep-qlora/` directory. It contains the adapter, checkpoints, training log, split manifest, actual environment versions, model manifest and loss plot. Use `--resume-from-checkpoint PATH` after a runtime disconnect. The notebook is distributed without cell outputs.

## Export and serving

The run's [export manifest](../ml/training_evidence/voxprep-qlora-v5/export_manifest.json) records the merged GGUF digests. Match the hash before serving a downloaded copy and verify the selected Agent on the presentation machine.

### B — merge FP16, convert, quantize on Kaggle (default)

```sh
python -m ml.export --run ml/runs/voxprep-qlora --output /kaggle/working/voxprep-export --llama-cpp /kaggle/working/llama.cpp --quantize-bin /kaggle/working/llama.cpp/build/bin/llama-quantize
```

The notebook builds the CPU conversion tool, records its source commit, verifies adapter hashes, reloads the original pinned base in FP16, merges PEFT weights, invokes `convert_hf_to_gguf.py`, and quantizes to Q4_K_M. Download only the final GGUF (approximately 2.5 GB; inspect actual size/hash) and run ZIP, avoiding full-weight downloads to the Mac. Allow extra disk and RAM for the export intermediates. The notebook removes only its own generated merged/F16 intermediates after verifying the final checksum.

Local configuration:

```sh
MODEL_PROVIDER=llama
MODEL_PATH=models/voxprep-Q4_K_M.gguf
# LORA_PATH is unset for a merged model.
```

### A — small adapter overlay

Use the pinned base revision's HF configuration directory, not an arbitrary latest config:

```sh
python /path/to/llama.cpp/convert_lora_to_gguf.py ml/runs/voxprep-qlora/adapter --base /path/to/pinned-hf-config --outfile ml/runs/voxprep-qlora/adapter.gguf --outtype f16
llama-server -m models/Qwen3-4B-Instruct-2507-Q4_K_M.gguf --lora ml/runs/voxprep-qlora/adapter.gguf --host 127.0.0.1 --port 8080 --jinja
```

The notebook supports `EXPORT_MODE="A"`, downloading only configuration/tokenizer files at the manifest's pinned revision. To launch through the app, set `LORA_PATH=ml/runs/voxprep-qlora/adapter.gguf` alongside the matching base `MODEL_PATH`. `scripts/dev.py` checks the adapter path and refuses to reuse an existing server unless `/lora-adapters` shows that exact adapter active at scale 1. Demo mode ignores `LORA_PATH`. Verify actual Qwen inference and output validation before selecting this route for the presentation; quantized overlay output can differ from merge-then-quantize.

## Training status contract

`evaluation.metadata.training_metadata` derives `status` from `ml/runs/voxprep-qlora/model_manifest.json` (or the configured output directory):

| Field | Without a completed manifest | With a completed manifest |
|---|---|---|
| `status` | `not_trained` | `training_completed` |
| `manifest_path` | Expected local run manifest path | Same path |
| `manifest_available` | `false` if missing/unreadable | `true` |
| `adapter_available` | `false` | Whether `adapter/adapter_model.safetensors` exists locally |
| `reviewed_examples` | Current corpus's valid review count | Count recorded in the real split manifest |
| `best_validation_loss` | Absent | Actual run's recorded value |

A partial/invalid manifest never changes status to trained. A valid manifest can record training even if the adapter has not been copied locally; `adapter_available` remains false in that case. Metadata prefers the reviewed source, then runtime drafts, then the legacy corpus, and reports actual counts independently of the configured expected count. `python -m evaluation.metadata` refreshes `evaluation/results/latest.json` without changing measured evaluation records. The local Methodology API reads current manifest evidence even when the saved snapshot is older; minimal packaged runtimes without training source keep a not-trained status. Preserve the full run and base GGUF for matched evaluation; training completion alone does not establish model quality or confirm the active server uses that model.

## Risks and limits

The draft data is narrow and repetitive, Cantonese quality needs native-speaker review, and fine-tuning can reduce general capability. Retrieval citations identify sources but do not prove every generated claim is supported. The evaluation tools report errors and human evidence separately. Quantization may change output quality and latency; evaluate the exported artifact that will actually run in the presentation. No training, review, or performance threshold is marked complete merely because the scripts exist.
