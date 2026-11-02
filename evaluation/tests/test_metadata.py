import json

from evaluation.metadata import training_metadata


def test_methodology_uses_pinned_configuration_and_real_draft_counts(tmp_path):
    (tmp_path / "ml").mkdir()
    config = {
        "base_model": "unit/base",
        "revision": "b" * 40,
        "output_dir": "ml/runs/test",
        "lora_r": 32,
        "seed": 42,
    }
    (tmp_path / "ml/config.json").write_text(json.dumps(config))
    result = training_metadata(tmp_path)
    assert result["base_revision"] == "b" * 40
    assert result["draft_examples"] == 0
    assert result["adapter_available"] is False
    assert result["configuration"]["lora_r"] == 32
    assert (
        result["configuration"]["implementation_settings"]["assistant_only_loss"]
        is True
    )
    assert result["model_card"]["base_model"] == "unit/base"


def test_methodology_does_not_claim_missing_adapter_is_available(tmp_path):
    (tmp_path / "ml").mkdir()
    config = {
        "base_model": "unit/base",
        "revision": "b" * 40,
        "output_dir": "ml/runs/test",
    }
    (tmp_path / "ml/config.json").write_text(json.dumps(config))
    run = tmp_path / config["output_dir"]
    run.mkdir(parents=True)
    manifest = {
        "status": "training_completed",
        "base_model": "unit/base",
        "base_revision": "b" * 40,
        "training_config": config,
        "dataset": {"review_validation": {"reviewed": 1500}},
        "best_validation_loss": 1.2,
    }
    (run / "model_manifest.json").write_text(json.dumps(manifest))
    result = training_metadata(tmp_path)
    assert result["status"] == "training_completed"
    assert result["reviewed_examples"] == 1500
    assert result["adapter_available"] is False
