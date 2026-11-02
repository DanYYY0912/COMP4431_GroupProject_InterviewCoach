import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "submission_package", Path(__file__).parents[1] / "package.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_excludes_credentials_runtime_data_and_large_weights(tmp_path):
    for name in [
        "README.md",
        ".env",
        ".env.example",
        "backend/app/main.py",
        "backend/.venv/secret.py",
        "data/voxprep.db",
        "models/base.gguf",
        "artifacts/token.txt",
        "frontend/node_modules/foo/index.js",
        "ml/dataset.jsonl",
    ]:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("test")
    assert set(module.submission_files(tmp_path)) == {
        Path("README.md"),
        Path(".env.example"),
        Path("backend/app/main.py"),
        Path("ml/dataset.jsonl"),
    }


def test_excludes_symlinks(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/leak.txt").symlink_to("/etc/passwd")
    assert list(module.submission_files(tmp_path)) == []


def trained_run(root):
    import hashlib
    import json
    import struct

    run = root / "ml/runs/voxprep-qlora"
    adapter = run / "adapter"
    adapter.mkdir(parents=True)
    config = {
        "peft_type": "LORA",
        "base_model_name_or_path": "Qwen/Qwen3-4B-Instruct-2507",
        "r": 32,
    }
    (adapter / "adapter_config.json").write_text(json.dumps(config))
    header = json.dumps(
        {
            "__metadata__": {"format": "pt"},
            "base_model.model.layer.q_proj.lora_A.weight": {
                "dtype": "F32",
                "shape": [2, 3],
                "data_offsets": [0, 24],
            },
            "base_model.model.layer.q_proj.lora_B.weight": {
                "dtype": "F32",
                "shape": [3, 2],
                "data_offsets": [24, 48],
            },
        }
    ).encode()
    (adapter / "adapter_model.safetensors").write_bytes(
        struct.pack("<Q", len(header)) + header + b"\0" * 48
    )
    (adapter / "training_args.bin").write_bytes(b"not-safe-to-package")
    (adapter / ".env").write_text("AZURE_SPEECH_KEY=private")
    (run / "training_log.jsonl").write_text('{"step":1,"loss":1.5}\n')
    (run / "environment.txt").write_text(
        "private-package @ https://secret@example.invalid/repo"
    )
    (run / "checkpoints").mkdir()
    (run / "checkpoints/base-model.safetensors").write_text("large base weights")
    manifest = {
        "status": "training_completed",
        "base_model": config["base_model_name_or_path"],
        "base_revision": "a" * 40,
        "adapter_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in adapter.iterdir()
        },
    }
    (run / "model_manifest.json").write_text(json.dumps(manifest))
    return run


def test_packages_verified_adapter_and_only_allowed_training_evidence(tmp_path):
    import json
    import zipfile

    trained_run(tmp_path)
    archive = module.package(tmp_path)
    with zipfile.ZipFile(archive) as zipped:
        names = set(zipped.namelist())
        prefix = "VoxPrep-HK/ml/runs/voxprep-qlora/"
        assert prefix + "adapter/adapter_model.safetensors" in names
        assert prefix + "adapter/adapter_config.json" in names
        assert prefix + "model_manifest.json" in names
        assert prefix + "training_log.jsonl" in names
        assert not any(
            name.endswith((".env", ".bin", "environment.txt", "base-model.safetensors"))
            for name in names
        )
        manifest = json.loads(zipped.read("VoxPrep-HK/SUBMISSION_MANIFEST.json"))
        assert manifest["trained_adapter_included"] is True


def test_rejects_changed_adapter_instead_of_packaging_unverified_weights(tmp_path):
    import pytest

    run = trained_run(tmp_path)
    (run / "adapter/adapter_model.safetensors").write_bytes(b"changed")
    with pytest.raises(ValueError, match="checksum"):
        module.package(tmp_path)


def test_rejects_manifest_path_traversal_and_symlinked_adapter(tmp_path):
    import json

    import pytest

    run = trained_run(tmp_path)
    manifest_path = run / "model_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["adapter_sha256"]["../secret.txt"] = "a" * 64
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="filename"):
        module.package(tmp_path)
    del manifest["adapter_sha256"]["../secret.txt"]
    manifest_path.write_text(json.dumps(manifest))
    (run / "adapter/adapter_config.json").unlink()
    (run / "adapter/adapter_config.json").symlink_to("/etc/passwd")
    with pytest.raises(ValueError, match="symlink"):
        module.package(tmp_path)


def test_incomplete_run_is_not_packaged(tmp_path):
    import json

    run = trained_run(tmp_path)
    path = run / "model_manifest.json"
    manifest = json.loads(path.read_text())
    manifest["status"] = "training"
    path.write_text(json.dumps(manifest))
    assert not any("runs" in p.parts for p in module.submission_files(tmp_path))


def test_rejects_credentials_embedded_in_training_metadata(tmp_path):
    import json

    import pytest

    run = trained_run(tmp_path)
    path = run / "model_manifest.json"
    manifest = json.loads(path.read_text())
    manifest["training_config"] = {"hub_token": "private-token"}
    path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="credential"):
        module.package(tmp_path)


def test_rejects_base_weights_disguised_as_an_adapter(tmp_path):
    import hashlib
    import json
    import struct

    import pytest

    run = trained_run(tmp_path)
    path = run / "adapter/adapter_model.safetensors"
    header = json.dumps(
        {
            "model.embed_tokens.weight": {
                "dtype": "F32",
                "shape": [2, 2],
                "data_offsets": [0, 16],
            }
        }
    ).encode()
    path.write_bytes(struct.pack("<Q", len(header)) + header + b"\0" * 16)
    manifest_path = run / "model_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["adapter_sha256"][path.name] = hashlib.sha256(
        path.read_bytes()
    ).hexdigest()
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="LoRA"):
        module.package(tmp_path)


def test_rejects_oversized_adapter_without_reading_it(tmp_path, monkeypatch):
    import pytest

    trained_run(tmp_path)
    monkeypatch.setattr(module, "MAX_ADAPTER_BYTES", 16)
    with pytest.raises(ValueError, match="size limit"):
        module.package(tmp_path)
