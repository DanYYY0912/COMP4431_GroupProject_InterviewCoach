"""Software validation only: approvals are artificial, test-only fixtures in tmp_path."""

import ast
import hashlib
import json
import random
import subprocess
import sys
from pathlib import Path

from ml.dataset import content_hash, write_jsonl

ROOT = Path(__file__).resolve().parents[2]


def test_kaggle_notebook_code_parses_and_has_no_saved_training_claims():
    notebook = json.loads((ROOT / "ml/VoxPrep_QLoRA.ipynb").read_text())
    assert notebook["nbformat"] == 4
    assert len({cell["id"] for cell in notebook["cells"]}) == len(notebook["cells"])
    for index, cell in enumerate(notebook["cells"]):
        if cell["cell_type"] == "code":
            ast.parse("".join(cell["source"]))
            assert cell["execution_count"] is None and cell["outputs"] == []
            assert notebook["cells"][index - 1]["cell_type"] == "markdown"


def test_validate_only_accepts_configured_480_row_test_fixture_without_gpu(tmp_path):
    # Deliberately artificial reviews verify the release gate in tests only.
    # They are never copied into ml/data or used for actual training/evaluation.
    config = json.loads((ROOT / "ml/config.json").read_text())
    config["data_dir"] = str(tmp_path / "splits")
    config["output_dir"] = str(tmp_path / "run")
    rng = random.Random(42)
    rows = []
    for i in range(config["expected_examples"]):
        family = str(i // 48)
        row = {
            "id": f"test-only-{i}",
            "task": "question",
            "language": "en-HK",
            "role_family": family,
            "source_id": f"test-source-{family}",
            "template_family": f"test-story-{i}",
            "messages": [
                {"role": "system", "content": "TEST FIXTURE ONLY"},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "answer": "".join(
                                rng.choices("abcdefghijklmnopqrstuvwxyz ", k=400)
                            )
                        }
                    ),
                },
                {
                    "role": "assistant",
                    "content": json.dumps(
                        {
                            "interviewer_text": "Tell me about your actions.",
                            "question_type": "opening",
                            "targeted_competencies": ["Python"],
                            "adaptive_follow_up_reason": None,
                            "citation_ids": ["test-source"],
                        }
                    ),
                },
            ],
            "provenance": {"license": "CC0-1.0", "kind": "artificial_test_fixture"},
            "reviews": [],
            "double_review_required": True,
        }
        row["content_sha256"] = content_hash(row)
        row["reviews"] = [
            {
                "reviewer": name,
                "decision": "approved",
                "reviewed_at": "2026-01-01T00:00:00+00:00",
                "content_sha256": row["content_sha256"],
            }
            for name in ("Test Fixture A", "Test Fixture B")
        ]
        rows.append(row)
    directory = Path(config["data_dir"])
    manifest = {"sha256": {}}
    for name, part in {
        "train": rows[:384],
        "validation": rows[384:432],
        "test": rows[432:],
    }.items():
        path = directory / f"{name}.jsonl"
        write_jsonl(path, part)
        manifest["sha256"][name] = hashlib.sha256(path.read_bytes()).hexdigest()
    (directory / "split_manifest.json").write_text(json.dumps(manifest))
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config))
    command = [
        sys.executable,
        "-m",
        "ml.train",
        "--config",
        str(config_path),
        "--validate-only",
    ]
    result = subprocess.run(
        command, cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
    assert "validated" in result.stdout
    assert not Path(config["output_dir"]).exists()
    rows[0]["reviews"] = []
    write_jsonl(directory / "train.jsonl", rows[:384])
    result = subprocess.run(
        command, cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert result.returncode != 0
    assert "human review" in result.stderr
