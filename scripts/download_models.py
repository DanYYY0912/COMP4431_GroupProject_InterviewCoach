"""Download pinned public model artifacts and verify their published LFS SHA-256."""

import hashlib
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def download(model):
    target = ROOT / "models" / model["filename"]
    target.parent.mkdir(exist_ok=True)
    if target.exists() and digest(target) == model["sha256"]:
        print("Verified existing", target.name, flush=True)
        return
    partial = target.with_suffix(target.suffix + ".partial")
    url = f"https://huggingface.co/{model['repo']}/resolve/{model['revision']}/{model['filename']}"
    print(
        f"Downloading {model['filename']} ({model['bytes'] / 1e9:.2f} GB)", flush=True
    )
    subprocess.run(
        [
            "curl",
            "--fail",
            "--location",
            "--retry",
            "3",
            "--connect-timeout",
            "20",
            "--silent",
            "--show-error",
            "--continue-at",
            "-",
            "--output",
            str(partial),
            url,
        ],
        check=True,
    )
    if partial.stat().st_size != model["bytes"] or digest(partial) != model["sha256"]:
        raise ValueError(
            f"Checksum mismatch: {partial}. Remove the partial file and retry."
        )
    partial.replace(target)
    print("Verified", target.name, flush=True)


if __name__ == "__main__":
    models = json.loads((ROOT / "scripts/models.json").read_text())
    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(download, models))
    (ROOT / "models/manifest.json").write_text(json.dumps(models, indent=2) + "\n")
