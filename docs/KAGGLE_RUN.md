# Kaggle GPU run — one command per step

`scripts/kaggle_train.py` turns a human-reviewed corpus into a private Kaggle GPU
run and pulls the training evidence back. It never publishes a dataset, kernel or
model, and it never relaxes the review gates inside `ml/dataset.py` /
`ml/train.py` (`--require-review`, hash, duplicate and split-leakage checks still
run in the notebook).

Nothing in this document has been executed against Kaggle during development: the
training corpus is still unreviewed, so only dry runs were used. Treat the commands
below as the procedure to follow once the corpus is human-reviewed.

## Prerequisites

| Item | Requirement |
|---|---|
| Kaggle account | Phone-verified, otherwise Internet and GPU are unavailable |
| Credential | `~/.kaggle/access_token` (`KGAT_...`, `chmod 600`). Never commit it or paste it into the notebook |
| Kaggle CLI | `kaggle` on `PATH`, or `uv` present (the script then runs `uv tool run --with six --from kaggle kaggle`). Override with `KAGGLE_CLI='...'` |
| Reviewed corpus | `ml/data/reviewed_examples.jsonl` with real human approvals; row count should match `expected_examples` in `ml/config.json` |
| GPU quota | Free T4 (≈14.6 GB) is enough for the NF4 QLoRA config; queues of 10+ minutes are normal |

Set the two names once and reuse them:

```bash
export OWNER=<your-kaggle-owner>
export KERNEL="$OWNER/voxprep-qlora"
export DATASET="$OWNER/voxprep-hk-reviewed"
```

## The four commands

```bash
# 1. Upload/refresh the PRIVATE reviewed corpus and verify the privacy flag.
python scripts/kaggle_train.py dataset --dataset "$DATASET" --reviewed-dir ml/data

# 2. Push the private GPU+internet kernel with the corpus attached.
python scripts/kaggle_train.py push --kernel "$KERNEL" --dataset "$DATASET"

# 3. Poll until COMPLETE/ERROR (default timeout 6 h, poll every 60 s).
python scripts/kaggle_train.py status --kernel "$KERNEL" --timeout 21600

# 4. Download the output and verify the training evidence.
python scripts/kaggle_train.py fetch --kernel "$KERNEL"
```

`watch` runs steps 3 and 4 in one process. Every subcommand prints the exact
Kaggle command it runs, prefixed with `+ `.

Add `--dry-run` to `dataset` and `push` to stage files, print the metadata and the
command, and stop before anything leaves the machine. That is the recommended
first move on a new account.

### What each step guarantees

* **dataset** copies `reviewed_examples.jsonl` plus any existing split artefacts
  (`train/validation/test.jsonl`, `split_manifest.json`) into a staging folder with
  a `dataset_manifest.json` recording each file's SHA-256, then runs
  `kaggle datasets create` (or `version` when the dataset already exists). It never
  passes `--public`, and after the upload it reads the metadata back with
  `kaggle datasets metadata` and refuses to continue unless Kaggle reports
  `isPrivate: true`. Kaggle omits default fields, so a missing flag counts as "not
  private".
* **push** writes `kernel-metadata.json` with `is_private: true`, `enable_gpu: true`,
  `enable_internet: true`, the dataset in `dataset_sources`, plus optional
  `model_sources` / `machine_shape`, next to a copy of `ml/VoxPrep_QLoRA.ipynb`, then
  runs `kaggle kernels push`.
* **status** polls `kaggle kernels status`, prints each state change with elapsed
  seconds, returns on `COMPLETE`, exits non-zero on `ERROR`/`CANCEL_*` (including the
  failure message) and on timeout. A queued kernel is not a failure: re-run `status`
  rather than pushing again, which would restart the run.
* **fetch** runs `kaggle kernels output -p <dir> -o`, then finds the run directory
  (unpacking `voxprep-training-evidence.zip` when only the archive was produced) and
  verifies `adapter/adapter_model.safetensors`, `loss.png`, `training_log.jsonl` and
  `model_manifest.json`, each non-empty, with `model_manifest.json` reporting
  `status == "training_completed"`. Anything missing is listed on stderr and the
  command exits `1`. On success it writes `fetch_report.json` with the SHA-256 of each
  artefact.

Local staging and output live under `ml/runs/kaggle/` (git-ignored via
`ml/.gitignore`'s `runs/`), never in tracked paths.

## Notebook behaviour

`ml/VoxPrep_QLoRA.ipynb` cell 1 now resolves its inputs in this order:

1. a private dataset containing this repository (attached with `--dataset`, detected
   by `ml/train.py` + `ml/config.json`), copied into `/kaggle/working` — an identical
   existing copy is reused so a interrupted run can be resumed;
2. a private dataset containing `reviewed_examples.jsonl` (uploaded by `dataset`),
   copied into `ml/data/` so `python -m ml.dataset` runs unchanged, and checked
   against the SHA-256 in the attached `dataset_manifest.json`;
3. the public fork branch, cloned exactly as before, for the case where the corpus is
   committed to a branch you control.

Everything after that cell is unchanged: `ml.dataset validate --require-review`,
`ml.dataset split`, `ml.train --validate-only`, the CUDA assert, training, provenance
inspection and route-B export. When the repository comes from a dataset there is no
`.git` history, so `source_revision.json` records the dataset name instead of a commit
hash (`"branch": null`).

The install cell keeps the image's driver-matched torch and installs the pins from
`ml/requirements-train.txt` (transformers 4.57.1, peft 0.17.1, accelerate 1.11.0,
bitsandbytes 0.48.1, datasets 4.3.0, …). The stock Kaggle image ships transformers 5.x,
which breaks `bitsandbytes` on import; the cell asserts the installed versions
afterwards so a silently unpinned install fails fast. Set `INSTALL_TORCH = True` only
after checking a torch change against the image's CUDA driver.

## After `fetch`

1. Copy the verified run directory to `ml/runs/voxprep-qlora/` (or point the app at
   where `fetch_report.json` says it is).
2. Keep `model_manifest.json`, `loss.png`, `training_log.jsonl` and the adapter; they
   are the evidence the Methodology screen and `scripts/package.py` read.
3. Run the held-out evaluation in `docs/EVALUATION.md`. A completed manifest is not an
   evaluation pass, and the loss curve alone does not establish quality.
4. Export follows the notebook (route B by default). Training, export and parity
   remain unverified until a real run produces them.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `kaggle: command not found`, `No module named 'six'` | The `kaggle` package forgets to declare `six`; use the `uv tool run --with six` form (automatic) or set `KAGGLE_CLI` |
| `401`/`Unauthenticated` | Token missing, expired or not `chmod 600`; re-authenticate and re-run |
| Dataset upload says slug already in use | The name exists on the account; `--mode version` (auto-detects) refreshes it, or pick another slug |
| `REFUSING: Kaggle does not report ... as private` | The metadata read-back lacked `isPrivate: true`; open the dataset settings, make it private, then re-run |
| `has status "QUEUED"` for a long time | Normal on free GPU; keep polling. Do not push a second version |
| Timed out waiting | The run continues on Kaggle; re-run `status`, or `fetch` once the page shows COMPLETE |
| `missing adapter/adapter_model.safetensors` | The notebook stopped before `trainer.save_model`; read `*.log` in the output directory and fix the failure instead of packaging it |
| `model_manifest.json status is ...` | The run did not finish training; the app must stay `not_trained` until a completed manifest exists |
| `bitsandbytes` import error on Kaggle | transformers 5.x is still installed; check the install cell asserted `4.57.1` and rerun from a clean session |
| `CUDA out of memory` on T4 | Keep batch 1 × accumulation 16 and `max_length` 2048; do not add a second process to GPU 0 |
