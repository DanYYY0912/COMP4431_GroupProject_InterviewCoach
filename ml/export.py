"""Merge a completed PEFT adapter and optionally convert it with local llama.cpp."""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--run", default="ml/runs/voxprep-qlora")
    p.add_argument("--output", default="models/voxprep")
    p.add_argument(
        "--llama-cpp",
        type=Path,
        help="Path to a built llama.cpp checkout; enables GGUF conversion",
    )
    p.add_argument("--quantize-bin", default="llama-quantize")
    args = p.parse_args()
    run = Path(args.run)
    out = Path(args.output)
    manifest = json.loads((run / "model_manifest.json").read_text())
    if manifest["status"] != "training_completed":
        raise SystemExit("A completed training run is required")
    adapter = run / "adapter"
    for name, digest in manifest["adapter_sha256"].items():
        if hashlib.sha256((adapter / name).read_bytes()).hexdigest() != digest:
            raise SystemExit(f"Adapter checksum mismatch: {name}")
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    base = AutoModelForCausalLM.from_pretrained(
        manifest["base_model"],
        revision=manifest["base_revision"],
        torch_dtype=torch.float16,
        device_map="auto",
    )
    merged = PeftModel.from_pretrained(base, str(adapter)).merge_and_unload()
    merged_dir = out / "merged"
    merged.save_pretrained(merged_dir, safe_serialization=True)
    AutoTokenizer.from_pretrained(adapter).save_pretrained(merged_dir)
    exports = {}
    if args.llama_cpp:
        converter = args.llama_cpp / "convert_hf_to_gguf.py"
        if not converter.is_file():
            raise SystemExit(f"Missing converter: {converter}")
        f16 = out / "voxprep-f16.gguf"
        q4 = out / "voxprep-Q4_K_M.gguf"
        subprocess.run(
            [
                sys.executable,
                str(converter),
                str(merged_dir),
                "--outfile",
                str(f16),
                "--outtype",
                "f16",
            ],
            check=True,
        )
        subprocess.run([args.quantize_bin, str(f16), str(q4), "Q4_K_M"], check=True)
        for path in (f16, q4):
            digest = hashlib.sha256()
            with path.open("rb") as file:
                for chunk in iter(lambda: file.read(1024 * 1024), b""):
                    digest.update(chunk)
            exports[path.name] = digest.hexdigest()
    (out / "export_manifest.json").write_text(
        json.dumps(
            {
                "source_run": str(run),
                "base_model": manifest["base_model"],
                "base_revision": manifest["base_revision"],
                "files": exports,
                "adapter_sha256": manifest["adapter_sha256"],
                "note": "Retain base model separately for matched A/B evaluation.",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
