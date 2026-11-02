"""Methodology metadata derived from local configuration and recorded artifacts."""

import hashlib
import json
from collections import Counter
from pathlib import Path

from ml.dataset import read_jsonl, validate_dataset


def training_metadata(root=Path(".")):
    config = json.loads((root / "ml/config.json").read_text())
    draft_path = root / "ml/data/drafts.jsonl"
    drafts = read_jsonl(draft_path) if draft_path.exists() else []
    reviews = validate_dataset(drafts)
    metadata = {
        "status": "not_trained",
        "base_model": config["base_model"],
        "base_revision": config["revision"],
        "draft_examples": len(drafts),
        "reviewed_examples": reviews["reviewed"],
        "adapter_available": False,
        "configuration": {
            **config,
            "implementation_settings": {
                "quantization": "4-bit NF4 with double quantization",
                "assistant_only_loss": True,
                "prompt_and_padding_label": -100,
                "precision": "BF16 when CUDA supports it; FP16 otherwise",
                "gradient_checkpointing": True,
                "optimizer": "paged_adamw_8bit",
                "checkpoint_selection": "Lowest validation loss; load_best_model_at_end",
                "execution": "One CUDA GPU; no training run recorded",
                "source": "ml/train.py",
            },
        },
        "dataset_provenance": {
            "path": "ml/data/drafts.jsonl",
            "sha256": hashlib.sha256(draft_path.read_bytes()).hexdigest()
            if drafts
            else None,
            "status": "Synthetic curriculum drafts; human review and deduplication required",
            "source_kinds": sorted({r["provenance"]["kind"] for r in drafts}),
            "licenses": sorted({r["provenance"]["license"] for r in drafts}),
            "language_counts": dict(Counter(r["language"] for r in drafts)),
            "task_counts": dict(Counter(r["task"] for r in drafts)),
            "independent_second_review_assignments": sum(
                r["double_review_required"] for r in drafts
            ),
            "reviewed_examples": reviews["reviewed"],
            "split_policy": "80/10/10; connected role, source and template groups stay together",
            "review_policy": "First human approval for every example; independent second review for at least 15% per full-corpus language/task stratum",
            "guide": "docs/DATASET.md",
        },
        "model_card": {
            "path": "docs/MODEL_CARD.md",
            "base_model": config["base_model"],
            "base_revision": config["revision"],
            "license": "Apache-2.0 (upstream Qwen base)",
            "adapter_status": "Not trained; no adapter available",
            "intended_use": "Local English/Cantonese interview practice for Hong Kong technology graduates",
            "excluded_uses": [
                "Hiring decisions or candidate ranking",
                "Emotion, appearance, personality, protected-trait or accent-quality scoring",
            ],
            "limitations": [
                "No fine-tuning or assessed model-quality results yet",
                "Citation identity and exact excerpts do not establish semantic support",
                "Cantonese quality requires human assessment",
            ],
        },
    }
    run = root / config["output_dir"]
    manifest_path = run / "model_manifest.json"
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text())
        if manifest.get("status") == "training_completed":
            metadata.update(
                {
                    "status": manifest["status"],
                    "base_model": manifest["base_model"],
                    "base_revision": manifest["base_revision"],
                    "reviewed_examples": manifest["dataset"]["review_validation"][
                        "reviewed"
                    ],
                    "adapter_available": (
                        run / "adapter/adapter_model.safetensors"
                    ).is_file(),
                    "best_validation_loss": manifest["best_validation_loss"],
                }
            )
            metadata["configuration"].update(manifest["training_config"])
            metadata["configuration"]["implementation_settings"]["execution"] = (
                "Training manifest recorded; held-out and human evaluation still required"
            )
            metadata["dataset_provenance"]["trained_dataset_manifest"] = manifest[
                "dataset"
            ]
            metadata["model_card"].update(
                {
                    "base_model": manifest["base_model"],
                    "base_revision": manifest["base_revision"],
                    "adapter_status": "Completed training manifest recorded; inspect adapter_available for local artifact presence",
                    "limitations": [
                        "Training completion alone does not demonstrate model quality",
                        "Citation identity and exact excerpts do not establish semantic support",
                        "Cantonese quality requires human assessment",
                    ],
                }
            )
    return metadata
