"""Methodology metadata derived from local configuration and recorded artifacts."""

import hashlib
import json
from collections import Counter
from pathlib import Path

from ml.dataset import read_jsonl, validate_dataset


def training_metadata(root=Path(".")):
    root = Path(root)
    config = json.loads((root / "ml/config.json").read_text())
    draft_path = next(
        (
            root / path
            for path in (
                "ml/data/reviewed_examples.jsonl",
                "ml/data/runtime_drafts.jsonl",
                "ml/data/drafts.jsonl",
            )
            if (root / path).is_file()
        ),
        root / "ml/data/runtime_drafts.jsonl",
    )
    drafts = read_jsonl(draft_path) if draft_path.exists() else []
    reviews = validate_dataset(drafts)
    metadata = {
        "status": "not_trained",
        "base_model": config["base_model"],
        "base_revision": config["revision"],
        "draft_examples": len(drafts),
        "reviewed_examples": reviews["reviewed"],
        "adapter_available": False,
        "manifest_path": str(Path(config["output_dir"]) / "model_manifest.json"),
        "manifest_available": False,
        "expected_examples": config.get("expected_examples"),
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
            "path": str(draft_path.relative_to(root)),
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
        try:
            manifest = json.loads(manifest_path.read_text())
            if manifest.get("status") == "training_completed":
                # A partial/corrupt file must never turn configuration into a training claim.
                from ml.train import validate_revision

                validate_revision(manifest["base_revision"])
                if not isinstance(manifest["base_model"], str) or not isinstance(
                    manifest["training_config"], dict
                ):
                    raise ValueError("Invalid training identity/configuration")
                reviewed = manifest["dataset"]["review_validation"]["reviewed"]
                if (
                    not isinstance(reviewed, int)
                    or isinstance(reviewed, bool)
                    or reviewed < 1
                ):
                    raise ValueError("Missing reviewed training examples")
                loss = manifest["best_validation_loss"]
                if loss is not None and (
                    not isinstance(loss, (float, int)) or isinstance(loss, bool)
                ):
                    raise ValueError("Invalid validation loss")
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            metadata["manifest_error"] = "Training manifest is unreadable or incomplete"
            return metadata
        metadata["manifest_available"] = True
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


def refresh_latest(root=Path(".")):
    """Update training evidence without modifying measured evaluation records."""
    root = Path(root)
    path = root / "evaluation/results/latest.json"
    data = (
        json.loads(path.read_text())
        if path.is_file()
        else {
            "status": "development_evidence_only",
            "provider": "configured_at_runtime",
            "evaluations": [],
            "limitations": [],
        }
    )
    data["training"] = training_metadata(root)
    if data["training"]["status"] == "training_completed":
        data["limitations"] = [
            line
            for line in data.get("limitations", [])
            if not line.startswith("No QLoRA training")
        ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    return data


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Refresh Methodology training metadata from local evidence"
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    refresh_latest(parser.parse_args().root)
