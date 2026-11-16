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


def test_missing_incomplete_or_invalid_manifest_stays_not_trained(tmp_path):
    (tmp_path / "ml").mkdir()
    config = {
        "base_model": "unit/base",
        "revision": "b" * 40,
        "output_dir": "ml/runs/test",
    }
    (tmp_path / "ml/config.json").write_text(json.dumps(config))
    run = tmp_path / config["output_dir"]
    run.mkdir(parents=True)
    path = run / "model_manifest.json"
    assert training_metadata(tmp_path)["status"] == "not_trained"
    for text in ('{"status": "training_completed"}', "{broken", "null"):
        path.write_text(text)
        result = training_metadata(tmp_path)
        assert result["status"] == "not_trained"
        assert result["adapter_available"] is False
        assert "manifest_error" in result


def test_refresh_preserves_evaluations_and_prefers_runtime_data(tmp_path):
    from evaluation.metadata import refresh_latest
    from ml.dataset import generate_drafts, write_jsonl

    (tmp_path / "ml").mkdir()
    config = {
        "base_model": "unit/base",
        "revision": "b" * 40,
        "output_dir": "ml/runs/test",
        "expected_examples": 480,
    }
    (tmp_path / "ml/config.json").write_text(json.dumps(config))
    rows = generate_drafts()[:2]
    write_jsonl(tmp_path / "ml/data/runtime_drafts.jsonl", rows)
    result_path = tmp_path / "evaluation/results/latest.json"
    result_path.parent.mkdir(parents=True)
    evaluations = [{"name": "diagnostic", "sample_size": 7}]
    result_path.write_text(
        json.dumps(
            {"evaluations": evaluations, "limitations": ["Human assessment pending"]}
        )
    )
    result = refresh_latest(tmp_path)
    assert result["evaluations"] == evaluations
    assert result["limitations"] == ["Human assessment pending"]
    assert (
        result["training"]["dataset_provenance"]["path"]
        == "ml/data/runtime_drafts.jsonl"
    )
    assert result["training"]["draft_examples"] == 2
    assert result["training"]["expected_examples"] == 480
    assert result["training"]["status"] == "not_trained"
    write_jsonl(tmp_path / "ml/data/reviewed_examples.jsonl", rows[:1])
    assert training_metadata(tmp_path)["draft_examples"] == 1
