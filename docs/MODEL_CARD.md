# VoxPrep HK model card

## Executive summary

VoxPrep HK currently has a real QLoRA training and export workflow but **no trained adapter, training loss, or fine-tuned model result**. The application can use its labelled deterministic demonstration provider or a separately configured local model. The planned base is Qwen3-4B-Instruct-2507. Training requires reviewed, independent data and a CUDA GPU in Colab or Kaggle. The workflow records hashes, configuration, environment, checkpoints, logs and loss plots only after an actual run, and retains the checkpoint with the best validation loss.

## Identity and intended use

| Field | Value |
|---|---|
| Planned base | `Qwen/Qwen3-4B-Instruct-2507` |
| Base license | Apache-2.0; see the upstream model card |
| Adapter | Not produced |
| Training status | Not run |
| Evaluated languages | None yet; English and Cantonese are the intended modes |
| Intended use | Classroom interview practice for Hong Kong technology graduates |
| Excluded use | Hiring/ranking, employability prediction, protected-trait, emotion, personality or accent-quality scoring |
| Deployment target | Local llama.cpp with Apple Metal; merged Q4_K_M GGUF |

The base model has 4B parameters and a non-thinking instruction interface, according to the [Qwen model card](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507). Upstream benchmark results are not VoxPrep evaluation evidence.

## Training configuration

`ml/config.json` records the proposed experiment. `ml/train.py` uses Transformers 4.57.1, PEFT, and bitsandbytes directly, with an explicit assistant-only token mask. This avoids relying on a model chat template to expose an assistant mask. It checks that the prompt token sequence is an exact prefix of the completed conversation and masks all prompt/padding labels with `-100`.

| Parameter | Setting |
|---|---|
| Quantization | 4-bit NF4, double quantization |
| LoRA | rank 32, alpha 64, dropout 0.05, all linear layers |
| Sequence limit | 2,048 tokens; oversize examples fail rather than silently lose target text |
| Effective batch | 32 on one CUDA GPU: microbatch 1 × 32 accumulation steps |
| Schedule | 3 epochs, learning rate 2e-4, cosine decay, 5% warm-up |
| Precision | BF16 when supported; FP16 otherwise |
| Memory | Gradient checkpointing, paged AdamW 8-bit |
| Selection | Lowest validation loss; evaluation and save every 25 optimizer steps |
| Seed | 42 |
| Reporting | Local logs only; no automatic third-party tracking |

The implementation follows the official [PEFT quantization guide](https://huggingface.co/docs/peft/developer_guides/quantization), [Transformers 4.57.1 Trainer API](https://huggingface.co/docs/transformers/v4.57.1/en/main_classes/trainer), and [chat-template interface](https://huggingface.co/docs/transformers/v4.57.1/en/chat_templating). GPU package versions are pinned in `ml/requirements-train.txt`; the GPU runtime itself has not been installed or executed here.

## Reproduce a training run

Open `ml/VoxPrep_QLoRA.ipynb` in a free Colab GPU runtime, or use Kaggle if Colab is unavailable. Upload the source package and real reviewed data. Follow `docs/DATASET.md` before executing any training cell.

```sh
python -m pip install -r ml/requirements-train.txt
python -m ml.train --config ml/config.json --validate-only
python -m ml.train --config ml/config.json
```

Keep the entire `ml/runs/voxprep-qlora/` directory. It contains the adapter, checkpoints, training log, split manifest, actual environment versions, model manifest and loss plot. Use `--resume-from-checkpoint PATH` after a runtime disconnect. The notebook intentionally has no execution counts or saved output because no training has occurred.

## Merge and local export

```sh
python -m ml.export --run ml/runs/voxprep-qlora --output models/voxprep --llama-cpp /absolute/path/to/llama.cpp
```

This verifies adapter hashes, reloads the original base at the recorded revision in FP16, merges PEFT weights, saves a complete Transformers model, invokes llama.cpp's `convert_hf_to_gguf.py`, and quantizes to Q4_K_M. A built llama.cpp checkout and `llama-quantize` must be available. Conversion and inference parity remain untested until a real adapter exists. Retain the base GGUF separately for evaluation; never replace it with the fine-tuned model.

## Risks and limits

The draft data is narrow and repetitive, Cantonese quality needs native-speaker review, and fine-tuning can reduce general capability. Retrieval citations identify sources but do not prove every generated claim is supported. The evaluation tools report errors and human evidence separately. Quantization may change output quality and latency; evaluate the exported artifact that will actually run in the presentation. No training, review, or performance threshold is marked complete merely because the scripts exist.
