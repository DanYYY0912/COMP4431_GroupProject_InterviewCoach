# VoxPrep HK model card

## Executive summary

VoxPrep HK currently has a real QLoRA training and export workflow but **no trained adapter, training loss, or fine-tuned model result**. The application can use its labelled deterministic demonstration provider or a separately configured local model. The planned base is Qwen3-4B-Instruct-2507. Training requires reviewed, independent data and a CUDA GPU in Kaggle (primary) or Colab (fallback). The workflow records hashes, configuration, environment, checkpoints, logs and loss plots only after an actual run, and retains the checkpoint with the best validation loss.

## Identity and intended use

| Field | Value |
|---|---|
| Planned base | `Qwen/Qwen3-4B-Instruct-2507` |
| Pinned base revision | `cdbee75f17c01a7cc42f958dc650907174af0554` |
| Base license | Apache-2.0; see the upstream model card |
| Adapter | Not produced |
| Training status | Not run |
| Evaluated languages | None yet; English and Cantonese are the intended modes |
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
| Schedule | 3 epochs, learning rate 2e-4, cosine decay, 5% warm-up |
| Precision | BF16 when supported; FP16 otherwise |
| Memory | Gradient checkpointing, paged AdamW 8-bit |
| Selection | Lowest validation loss; evaluation and save every 10 optimizer steps; log every 2 |
| Seed | 42 |
| Reporting | Local logs only; no automatic third-party tracking |

The implementation follows the official [PEFT quantization guide](https://huggingface.co/docs/peft/developer_guides/quantization), [Transformers 4.57.1 Trainer API](https://huggingface.co/docs/transformers/v4.57.1/en/main_classes/trainer), and [chat-template interface](https://huggingface.co/docs/transformers/v4.57.1/en/chat_templating). GPU package versions are pinned in `ml/requirements-train.txt`; the GPU runtime itself has not been installed or executed here.

## Reproduce a training run

Open `ml/VoxPrep_QLoRA.ipynb` in Kaggle with phone verification, Internet and a CUDA GPU enabled; Colab is the fallback. The first code cell clones the public fork at the selected `BRANCH` and records its commit. Publish real `ml/data/reviewed_examples.jsonl` on that branch first; splits are created in the notebook with seed 42, so no split files need committing. See [EXTERNAL_SETUP.md](EXTERNAL_SETUP.md) and [DATASET.md](DATASET.md).

`expected_examples` is **480**, the planned WS2 count (WS2 generation is not part of WS5 and is still pending here). Confirm the actual reviewed count before running. Effective batch 16 gives roughly 24 optimizer steps per epoch for a 384-row training split; evaluation every 10 and logging every 2 provide enough observations for the smaller corpus. No data gate was loosened. T4 uses FP16 automatically; BF16 is used only on supported CUDA GPUs.

```sh
python -m pip install -r ml/requirements-train.txt
python -m ml.train --config ml/config.json --validate-only
python -m ml.train --config ml/config.json
```

Keep the entire `ml/runs/voxprep-qlora/` directory. It contains the adapter, checkpoints, training log, split manifest, actual environment versions, model manifest and loss plot. Use `--resume-from-checkpoint PATH` after a runtime disconnect. The notebook intentionally has no execution counts or saved output because no training has occurred.

## Export decision: route B selected; route A remains unverified

Diagnostic preflight on 16 November 2026 checked the official [LoRA converter](https://github.com/ggml-org/llama.cpp/blob/master/convert_lora_to_gguf.py), [server options](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md) and [conversion/inference tests](https://github.com/ggml-org/llama.cpp/blob/master/tests/test-lora-conversion-inference.sh). Upstream documents `--lora`, and its runtime applies adapters separately from F16/quantized base inference. The converter takes the PEFT adapter and matching HF base configuration through `--base`; full base weights are not needed for route A conversion. This documents upstream capability, **not** a successful Qwen3-4B experiment.

The local preflight could not start a real conversion/inference test: no trained adapter exists, `llama-server` is absent from PATH, and torch/transformers/peft/safetensors are not installed in the project environment. It was stopped at these missing prerequisites within the plan's 30-minute cap; no 30-minute runtime experiment or inference parity is claimed. The delivery therefore selects the existing route B, with all GPU/export steps still pending a real run.

### B — merge FP16, convert, quantize on Kaggle (default)

```sh
python -m ml.export --run ml/runs/voxprep-qlora --output /kaggle/working/voxprep-export --llama-cpp /kaggle/working/llama.cpp --quantize-bin /kaggle/working/llama.cpp/build/bin/llama-quantize
```

The notebook builds the CPU conversion tool, records its source commit, verifies adapter hashes, reloads the original pinned base in FP16, merges PEFT weights, invokes `convert_hf_to_gguf.py`, and quantizes to Q4_K_M. Download only the final GGUF (approximately 2.5 GB; inspect actual size/hash) and run ZIP, avoiding full-weight downloads to the Mac. Conversion is still unexecuted; sufficient temporary disk and RAM/VRAM are required. The notebook removes only its own generated merged/F16 intermediates after verifying the final checksum.

Local configuration:

```sh
MODEL_PROVIDER=llama
MODEL_PATH=models/voxprep-Q4_K_M.gguf
# LORA_PATH is unset for a merged model.
```

### A — small adapter overlay (optional after real validation)

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
