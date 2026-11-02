"""Create a reproducible source ZIP using a narrow allowlist, excluding user data."""

from __future__ import annotations

import hashlib
import json
import re
import struct
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = {
    ".gitignore",
    ".dockerignore",
    ".env.example",
    "data/demo-job.txt",
    "Makefile",
    "Dockerfile",
    "compose.yaml",
    "README.md",
    "PROGRESS.md",
    "LICENSE",
    "requirements.lock",
    "pytest.ini",
}
SOURCE_DIRS = {
    "backend",
    "frontend",
    "contracts",
    "docs",
    "knowledge",
    "ml",
    "evaluation",
    "scripts",
    "e2e",
    ".github",
    "presentation",
}
EXCLUDE_DIRS = {
    ".venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".cache",
    "dist",
    "test-results",
    "playwright-report",
    "checkpoints",
    "runs",
    "outputs",
    "build",
}
EXCLUDE_SUFFIXES = {
    ".db",
    ".sqlite",
    ".sqlite3",
    ".gguf",
    ".bin",
    ".safetensors",
    ".pyc",
    ".pem",
    ".key",
    ".partial",
    ".log",
}


TRAINING_RUN = Path("ml/runs/voxprep-qlora")
MAX_ADAPTER_BYTES = 512 * 1024 * 1024
ADAPTER_FILES = {
    "adapter_model.safetensors",
    "adapter_config.json",
    "README.md",
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "added_tokens.json",
    "vocab.json",
    "merges.txt",
}
TRAINING_EVIDENCE = {
    "config.json",
    "split_manifest.json",
    "training_log.jsonl",
    "loss.png",
    "checkpoints/trainer_state.json",
    "checkpoints/train_results.json",
    "checkpoints/validation_results.json",
    "checkpoints/all_results.json",
}
SECRET_KEYS = {
    "api_key",
    "azure_speech_key",
    "hf_token",
    "hub_token",
    "access_token",
    "refresh_token",
    "client_secret",
    "password",
    "authorization",
}


def reject_secret_fields(value):
    if isinstance(value, dict):
        for key, item in value.items():
            if str(key).casefold() in SECRET_KEYS and item:
                raise ValueError(
                    "Training evidence contains a credential field; remove it before packaging"
                )
            reject_secret_fields(item)
    elif isinstance(value, list):
        for item in value:
            reject_secret_fields(item)


def training_file(root, relative, limit=25_000_000):
    path = root / relative
    if any(
        (root / Path(*relative.parts[:i])).is_symlink()
        for i in range(1, len(relative.parts) + 1)
    ):
        raise ValueError(f"Training artifacts cannot be symlinks: {relative}")
    if not path.is_file() or path.stat().st_size > limit:
        raise ValueError(
            f"Training artifact is missing or exceeds its size limit: {relative}"
        )
    return path


def verify_lora_tensors(path):
    # Inspect the safe tensor header without loading weights or trusting pickle.
    with path.open("rb") as handle:
        prefix = handle.read(8)
        if len(prefix) != 8:
            raise ValueError("Adapter is not a safetensors file")
        header_size = struct.unpack("<Q", prefix)[0]
        if not 0 < header_size <= 4 * 1024 * 1024:
            raise ValueError("Invalid adapter tensor header size")
        tensors = json.loads(handle.read(header_size))
    if not isinstance(tensors, dict):
        raise TypeError("Invalid adapter tensor header")
    reject_secret_fields(tensors.get("__metadata__", {}))
    names = [name for name in tensors if name != "__metadata__"]
    if (
        not names
        or not any(".lora_A." in name for name in names)
        or not any(".lora_B." in name for name in names)
    ):
        raise ValueError("Expected LoRA A/B adapter tensors")
    if any(".lora_A." not in name and ".lora_B." not in name for name in names):
        raise ValueError(
            "Adapter contains non-LoRA tensors; base model weights are excluded"
        )
    payload_size = path.stat().st_size - 8 - header_size
    for name in names:
        tensor = tensors[name]
        shape, offsets = tensor.get("shape", []), tensor.get("data_offsets", [])
        if (
            len(shape) != 2
            or len(offsets) != 2
            or not 0 <= offsets[0] <= offsets[1] <= payload_size
        ):
            raise ValueError("Invalid LoRA tensor dimensions or offsets")


def verified_training_files(root):
    manifest_rel = TRAINING_RUN / "model_manifest.json"
    if not (root / manifest_rel).exists():
        return {}
    manifest_path = training_file(root, manifest_rel)
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("status") != "training_completed":
        return {}
    reject_secret_fields(manifest)
    if not re.fullmatch(r"[0-9a-f]{40}", manifest.get("base_revision", "")):
        raise ValueError("Completed model manifest must pin an immutable base revision")
    hashes = manifest.get("adapter_sha256", {})
    if (
        not isinstance(hashes, dict)
        or not {"adapter_model.safetensors", "adapter_config.json"} <= hashes.keys()
    ):
        raise ValueError(
            "Completed model manifest must include adapter weights and config checksums"
        )
    selected = {manifest_rel: hashlib.sha256(manifest_path.read_bytes()).hexdigest()}
    total = 0
    for name, expected in hashes.items():
        if (
            not isinstance(name, str)
            or Path(name).name != name
            or "/" in name
            or "\\" in name
        ):
            raise ValueError("Model manifest contains an invalid adapter filename")
        if name not in ADAPTER_FILES:
            continue  # Never package pickled training_args, secrets, or other weights.
        if not isinstance(expected, str) or not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise ValueError("Invalid adapter SHA-256 checksum")
        relative = TRAINING_RUN / "adapter" / name
        path = training_file(
            root,
            relative,
            MAX_ADAPTER_BYTES if name == "adapter_model.safetensors" else 25_000_000,
        )
        with path.open("rb") as handle:
            actual = hashlib.file_digest(handle, "sha256").hexdigest()
        if actual != expected:
            raise ValueError(f"Adapter checksum mismatch: {name}")
        if path.suffix == ".json":
            reject_secret_fields(json.loads(path.read_text()))
        selected[relative] = actual
        total += path.stat().st_size
    if total > MAX_ADAPTER_BYTES:
        raise ValueError(
            "Adapter exceeds the 512 MiB submission limit; never substitute base weights"
        )
    config = json.loads(
        (root / TRAINING_RUN / "adapter/adapter_config.json").read_text()
    )
    if config.get("peft_type") != "LORA" or config.get(
        "base_model_name_or_path"
    ) != manifest.get("base_model"):
        raise ValueError(
            "Adapter config does not match the completed LoRA model manifest"
        )
    verify_lora_tensors(root / TRAINING_RUN / "adapter/adapter_model.safetensors")
    for name in sorted(TRAINING_EVIDENCE):
        relative = TRAINING_RUN / name
        if not (root / relative).exists():
            continue
        path = training_file(root, relative)
        content = path.read_bytes()
        if path.suffix == ".json":
            reject_secret_fields(json.loads(content))
        elif path.suffix == ".jsonl":
            for line in content.splitlines():
                if line.strip():
                    reject_secret_fields(json.loads(line))
        selected[relative] = hashlib.sha256(content).hexdigest()
    return selected


def submission_files(root, include_training=True):
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if path.is_symlink() or not path.is_file():
            continue
        if rel.parts[0] not in SOURCE_DIRS and str(rel) not in ROOT_FILES:
            continue
        if any(
            part in EXCLUDE_DIRS or part.endswith(".egg-info") for part in rel.parts
        ):
            continue
        if path.name.startswith(".env") and path.name != ".env.example":
            continue
        if path.suffix in EXCLUDE_SUFFIXES or path.stat().st_size > 25_000_000:
            continue
        yield rel
    if include_training:
        yield from verified_training_files(root)


def package(root=ROOT):
    out = root / "artifacts"
    out.mkdir(exist_ok=True)
    training = verified_training_files(root)
    files = sorted(
        set(submission_files(root, include_training=False)) | training.keys()
    )
    checksums = {}
    destination = out / "VoxPrep-HK-source.zip"
    temporary = out / ".VoxPrep-HK-source.zip.partial"
    try:
        with zipfile.ZipFile(
            temporary, "w", compression=zipfile.ZIP_DEFLATED
        ) as archive:
            for path in files:
                content = (root / path).read_bytes()
                digest = hashlib.sha256(content).hexdigest()
                if path in training and training[path] != digest:
                    raise ValueError(
                        f"Training artifact changed during packaging: {path}"
                    )
                checksums[str(path)] = digest
                info = zipfile.ZipInfo(
                    str(Path("VoxPrep-HK") / path), date_time=(2026, 11, 2, 0, 0, 0)
                )
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                archive.writestr(info, content)
            manifest = {
                "format_version": 1,
                "files": checksums,
                "trained_adapter_included": bool(training),
                "training_manifest": str(TRAINING_RUN / "model_manifest.json")
                if training
                else None,
                "limitations": "Review PROGRESS.md for unmet assessed release gates. A packaged adapter proves artifact integrity, not model quality. Base weights, checkpoints, credentials and personal session data are excluded.",
            }
            manifest_info = zipfile.ZipInfo(
                "VoxPrep-HK/SUBMISSION_MANIFEST.json", date_time=(2026, 11, 2, 0, 0, 0)
            )
            manifest_info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(manifest_info, json.dumps(manifest, indent=2))
        with zipfile.ZipFile(temporary) as archive:
            if archive.testzip() is not None:
                raise RuntimeError("ZIP integrity check failed")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    (out / "VoxPrep-HK-source.zip.sha256").write_text(f"{digest}  {destination.name}\n")
    print(
        f"{destination}\n{len(files)} files; {destination.stat().st_size:,} bytes; SHA256 {digest}"
    )
    return destination


if __name__ == "__main__":
    package()
