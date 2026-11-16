"""One-command Kaggle GPU training for the reviewed VoxPrep corpus.

Four subcommands cover the whole path:

* ``dataset`` uploads the human-reviewed corpus as a **private** Kaggle dataset
  and verifies the privacy flag by reading the metadata back.
* ``push`` writes a private GPU + internet kernel-metadata.json next to a copy of
  ``ml/VoxPrep_QLoRA.ipynb`` and pushes it.
* ``status`` polls the kernel until it is COMPLETE/ERROR or the timeout expires.
* ``fetch`` downloads the kernel output and refuses to report success unless the
  adapter, loss curve, training log and completed manifest are all present.

``watch`` is ``status`` + ``fetch`` in one process.

Nothing here publishes a dataset, kernel or model. The training gates inside
``ml/dataset.py`` and ``ml/train.py`` (``--require-review``) are never bypassed:
this script only moves data and artefacts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = Path("ml/VoxPrep_QLoRA.ipynb")
CONFIG = Path("ml/config.json")
DATA_FILE = "reviewed_examples.jsonl"
SPLIT_FILES = ("train.jsonl", "validation.jsonl", "test.jsonl", "split_manifest.json")
REQUIRED_ARTIFACTS = (
    "adapter/adapter_model.safetensors",
    "loss.png",
    "training_log.jsonl",
    "model_manifest.json",
)
COMPLETED_STATUS = "training_completed"
OK_STATUSES = frozenset({"COMPLETE"})
FAILED_STATUSES = frozenset({"ERROR", "CANCEL_ACKNOWLEDGED", "CANCEL_REQUESTED"})
SLUG_RE = re.compile(r"[a-z0-9][a-z0-9-]{3,48}[a-z0-9]")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def count_jsonl_rows(path: Path) -> int:
    with Path(path).open(encoding="utf-8") as handle:
        return sum(1 for line in handle if line.strip())


def parse_ref(value: str) -> tuple[str, str]:
    """Validate a Kaggle ``owner/slug`` reference (argparse type)."""
    parts = value.split("/")
    if len(parts) != 2 or not all(parts):
        raise argparse.ArgumentTypeError(
            f"expected <owner>/<slug>, for example owner/voxprep-qlora; got {value!r}"
        )
    owner, slug = parts
    if not SLUG_RE.fullmatch(slug):
        raise argparse.ArgumentTypeError(
            f"invalid Kaggle slug {slug!r}: use 6-50 lowercase letters, digits or "
            "hyphens, starting and ending with a letter or digit"
        )
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{1,49}", owner):
        raise argparse.ArgumentTypeError(f"invalid Kaggle owner {owner!r}")
    return owner, slug


TITLE_WORDS = {"voxprep": "VoxPrep", "hk": "HK", "qlora": "QLoRA", "kaggle": "Kaggle"}


def title_for_slug(slug: str) -> str:
    """Human title that kaggle-cli's slugify() maps back onto ``slug``."""
    words = [
        TITLE_WORDS.get(word, word.capitalize()) for word in slug.split("-") if word
    ]
    title = " ".join(words)
    return title if len(title) >= 5 else f"{title} run"


def kaggle_cli(environ=None) -> list[str]:
    """Resolve the Kaggle CLI, honouring ``KAGGLE_CLI`` for a pinned invocation."""
    environ = os.environ if environ is None else environ
    override = environ.get("KAGGLE_CLI")
    if override:
        return shlex.split(override)
    found = shutil.which("kaggle")
    if found:
        return [found]
    uv = shutil.which("uv")
    if uv is None:
        candidate = Path.home() / ".local/bin/uv"
        uv = str(candidate) if candidate.is_file() else None
    if uv:
        # The kaggle package imports six without declaring it as a dependency.
        return [uv, "tool", "run", "--with", "six", "--from", "kaggle", "kaggle"]
    raise SystemExit(
        "No Kaggle CLI found. Install it (uv tool install --with six kaggle) or set "
        "KAGGLE_CLI='uv tool run --with six --from kaggle kaggle'."
    )


def command_line(args, *, cli=None) -> list[str]:
    return [*(cli if cli is not None else kaggle_cli()), *[str(a) for a in args]]


def report(command) -> None:
    print("+ " + shlex.join([str(part) for part in command]), flush=True)


def run_command(command, *, dry_run=False, capture=False) -> str:
    """Print the exact command, then run it (or only print it when dry-running)."""
    report(command)
    if dry_run:
        return ""
    result = subprocess.run(command, check=True, text=True, capture_output=capture)
    return result.stdout if capture else ""


def dataset_metadata(*, slug, title, description="", keywords=()) -> dict:
    """datasets-metadata.json body. Privacy is chosen by the CLI flag, not here."""
    if not 6 <= len(title) <= 50:
        raise SystemExit(
            f"Dataset title must be 6-50 characters for Kaggle; got {title!r}"
        )
    return {
        "id": slug,
        "title": title,
        "licenses": [{"name": "other"}],
        "description": description,
        "keywords": list(keywords),
    }


def validate_model_source(value: str) -> str:
    """Kaggle model sources are owner/slug/framework/instance/version."""
    if value.count("/") != 4 or not all(value.split("/")):
        raise argparse.ArgumentTypeError(
            "expected owner/slug/framework/instance/version, for example "
            f"qwen-lm/qwen3/transformers/4b/1; got {value!r}"
        )
    return value


def kernel_metadata(
    *,
    slug,
    title,
    code_file,
    dataset_sources=(),
    model_sources=(),
    machine_shape=None,
) -> dict:
    """kernel-metadata.json body: private, GPU, internet, attached sources."""
    if len(title) < 5:
        raise SystemExit(
            f"Kernel title must be at least five characters; got {title!r}"
        )
    for source in dataset_sources:
        parse_ref(source)
    meta = {
        "id": slug,
        "title": title,
        "code_file": code_file,
        "language": "python",
        "kernel_type": "notebook",
        "is_private": True,
        "enable_gpu": True,
        "enable_tpu": False,
        "enable_internet": True,
        "keywords": [],
        "dataset_sources": list(dataset_sources),
        "competition_sources": [],
        "kernel_sources": [],
        "model_sources": list(model_sources),
    }
    if machine_shape:
        meta["machine_shape"] = machine_shape
    return meta


def dataset_upload_command(stage, *, exists, notes=None) -> list[str]:
    """``datasets create`` or ``datasets version`` - never ``--public``."""
    base = command_line(["datasets"])
    if exists:
        command = [
            *base,
            "version",
            "-p",
            str(stage),
            "--dir-mode",
            "zip",
            "-m",
            notes or f"reviewed corpus refresh {datetime.now(UTC).isoformat()}",
        ]
    else:
        command = [*base, "create", "-p", str(stage), "--dir-mode", "zip"]
    assert "--public" not in command and "-u" not in command
    return command


def _resolve(path) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else (ROOT / candidate)


def read_dataset_metadata(slug, probe_dir) -> str | None:
    """Download dataset metadata; ``None`` when the dataset does not exist yet."""
    probe = Path(probe_dir)
    probe.mkdir(parents=True, exist_ok=True)
    target = probe / "dataset-metadata.json"
    target.unlink(missing_ok=True)
    try:
        run_command(
            command_line(["datasets", "metadata", slug, "-p", str(probe)]), capture=True
        )
    except subprocess.CalledProcessError:
        return None
    return target.read_text() if target.is_file() else None


def is_private(metadata_text: str) -> bool:
    """Kaggle omits default fields, so a private dataset must carry isPrivate=true."""
    data = json.loads(metadata_text)
    info = data.get("info", data)
    return info.get("isPrivate") is True


def stage_dataset(source_dir, stage_dir, *, slug, title, description="") -> Path:
    """Copy the reviewed corpus (plus any split artefacts) into an upload folder."""
    source = Path(source_dir)
    stage = Path(stage_dir)
    reviewed = source / DATA_FILE
    if not reviewed.is_file():
        raise SystemExit(
            f"{reviewed} not found. Only a human-reviewed corpus may be uploaded; "
            "generate and review it with `python -m ml.review` first."
        )
    if stage.resolve() == source.resolve() or source.resolve().is_relative_to(
        stage.resolve()
    ):
        raise SystemExit(
            f"--stage-dir {stage} must not be the corpus directory or one of its "
            "parents; the upload folder is rebuilt from scratch on every run."
        )
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True, exist_ok=True)
    for name in (DATA_FILE, *SPLIT_FILES):
        path = source / name
        if path.is_file():
            shutil.copy2(path, stage / name)
    files = {
        path.name: {"sha256": sha256_file(path), "bytes": path.stat().st_size}
        for path in sorted(stage.iterdir())
        if path.is_file()
    }
    manifest = {
        "created_at": datetime.now(UTC).isoformat(),
        "source": str(source),
        "rows": count_jsonl_rows(stage / DATA_FILE),
        "files": files,
    }
    (stage / "dataset_manifest.json").write_text(json.dumps(manifest, indent=2))
    (stage / "dataset-metadata.json").write_text(
        json.dumps(
            dataset_metadata(
                slug=slug, title=title, description=description, keywords=["nlp"]
            ),
            indent=2,
        )
    )
    return stage


def command_dataset(args) -> None:
    owner, slug_part = parse_ref(args.dataset)
    slug = f"{owner}/{slug_part}"
    source = _resolve(args.reviewed_dir)
    stage = _resolve(args.stage_dir)
    title = args.title or "VoxPrep HK reviewed training corpus"
    reviewed = source / DATA_FILE
    if not reviewed.is_file():
        raise SystemExit(
            f"{reviewed} not found. Upload only a human-reviewed corpus; "
            "`python -m ml.review` produces it."
        )
    rows = count_jsonl_rows(reviewed)
    print(f"Reviewed corpus: {reviewed} ({rows} rows, sha256 {sha256_file(reviewed)})")
    expected = None
    config_path = ROOT / CONFIG
    if config_path.is_file():
        expected = json.loads(config_path.read_text()).get("expected_examples")
    if expected and rows != expected:
        print(
            f"WARNING: {rows} reviewed rows but ml/config.json expects {expected}. "
            "The dataset gate will reject the run until the config or the corpus matches.",
            file=sys.stderr,
        )
    stage_dataset(
        source,
        stage,
        slug=slug,
        title=title,
        description=args.description,
    )
    exists = False
    if args.mode == "auto":
        exists = read_dataset_metadata(slug, stage / "probe") is not None
    elif args.mode == "version":
        exists = True
    command = dataset_upload_command(stage, exists=exists, notes=args.notes)
    if args.dry_run:
        print((stage / "dataset-metadata.json").read_text())
        run_command(command, dry_run=True)
        print("Dry run: nothing uploaded.")
        return
    run_command(command)
    metadata_text = read_dataset_metadata(slug, stage / "verify")
    if metadata_text is None:
        raise SystemExit(
            f"Uploaded {slug} but could not read its metadata back. Open "
            f"https://www.kaggle.com/datasets/{slug}/settings and confirm the dataset "
            "is private before attaching it to any kernel."
        )
    (stage / "dataset-metadata.readback.json").write_text(metadata_text)
    if not is_private(metadata_text):
        raise SystemExit(
            f"REFUSING: Kaggle does not report {slug} as private. Delete or make it "
            "private before training: public training data would expose every reviewer "
            "name and record in the corpus."
        )
    print(f"Verified private dataset: https://www.kaggle.com/datasets/{slug}")


def command_push(args) -> None:
    owner, slug_part = parse_ref(args.kernel)
    slug = f"{owner}/{slug_part}"
    notebook = _resolve(args.notebook)
    if not notebook.is_file():
        raise SystemExit(f"Notebook not found: {notebook}")
    stage = _resolve(args.stage_dir)
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    code_file = notebook.name
    shutil.copy2(notebook, stage / code_file)
    meta = kernel_metadata(
        slug=slug,
        title=args.title or title_for_slug(slug_part),
        code_file=code_file,
        dataset_sources=args.dataset or [],
        model_sources=args.model_source or [],
        machine_shape=args.machine_shape,
    )
    (stage / "kernel-metadata.json").write_text(json.dumps(meta, indent=2))
    command = command_line(["kernels", "push", "-p", str(stage)])
    if args.max_runtime_seconds:
        command += ["-t", str(args.max_runtime_seconds)]
    if args.accelerator:
        command += ["--accelerator", args.accelerator]
    print((stage / "kernel-metadata.json").read_text())
    if args.dry_run:
        run_command(command, dry_run=True)
        print("Dry run: nothing pushed.")
        return
    run_command(command)
    print(
        f"Pushed private kernel https://www.kaggle.com/code/{slug}. "
        f"Poll it with: python scripts/kaggle_train.py status --kernel {slug}"
    )


def parse_status(output: str) -> tuple[str, str]:
    match = re.search(r'has status "([A-Z_]+)"', output or "")
    if match is None:
        raise SystemExit(f"Unexpected `kaggle kernels status` output: {output!r}")
    failure = re.search(r'Failure message: "(.*)"', output)
    return match.group(1), failure.group(1) if failure else ""


def poll_until_done(
    status_command, *, timeout, interval, sleep=time.sleep, clock=time.monotonic
) -> str:
    """Poll ``status_command`` until a terminal state, a timeout or a failure."""
    start = clock()
    previous = None
    while True:
        status, message = parse_status(status_command())
        elapsed = clock() - start
        if status != previous:
            print(f"[{elapsed:.0f}s] {status}" + (f" - {message}" if message else ""))
            previous = status
        if status in OK_STATUSES:
            return status
        if status in FAILED_STATUSES:
            detail = f" ({message})" if message else ""
            raise SystemExit(f"Kaggle run failed with status {status}{detail}")
        if elapsed >= timeout:
            raise SystemExit(
                f"Timed out after {timeout:.0f}s waiting for the Kaggle run; last status "
                f"{status}. Free GPU queues are often longer than ten minutes; re-run "
                "status (the run keeps going) instead of pushing again."
            )
        sleep(interval)


def kernel_status(kernel) -> str:
    """``kaggle kernels status`` with an actionable message instead of a traceback."""
    try:
        return run_command(command_line(["kernels", "status", kernel]), capture=True)
    except subprocess.CalledProcessError as error:
        raise SystemExit(
            f"`kaggle kernels status {kernel}` failed with exit {error.returncode}. "
            "Check the owner/slug, that the private kernel exists under this account, "
            "and that ~/.kaggle/access_token is valid."
        ) from error


def command_status(args) -> None:
    status = poll_until_done(
        lambda: kernel_status(args.kernel),
        timeout=args.timeout,
        interval=args.interval,
    )
    print(f"{args.kernel} finished with status {status}")


def safe_extract(archive: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    root = target.resolve()
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.namelist():
            if not (root / member).resolve().is_relative_to(root):
                raise SystemExit(f"Refusing to extract {member!r} outside {target}")
        bundle.extractall(target)


def locate_run_root(directory) -> Path:
    """Find the directory holding model_manifest.json, unpacking the evidence ZIP."""
    base = Path(directory)
    roots = sorted({path.parent for path in base.rglob("model_manifest.json")})
    if not roots:
        for archive in sorted(base.rglob("*.zip")):
            safe_extract(archive, base / "_unpacked" / archive.stem)
        roots = sorted({path.parent for path in base.rglob("model_manifest.json")})
    if not roots:
        raise SystemExit(
            f"No model_manifest.json under {base}. The kernel either produced no "
            "output or its output listing is empty; download it from the notebook "
            "page and keep the failure."
        )
    preferred = [path for path in roots if path.name == "voxprep-qlora"]
    print(f"Run directory: {(preferred or roots)[0]}")
    return (preferred or roots)[0]


def verify_run(run_root, expected_status=COMPLETED_STATUS) -> list[str]:
    """Return every problem that makes this run unusable as training evidence."""
    root = Path(run_root)
    problems = []
    for relative in REQUIRED_ARTIFACTS:
        path = root / relative
        if not path.is_file():
            problems.append(f"missing {relative}")
        elif path.stat().st_size == 0:
            problems.append(f"empty {relative}")
    manifest = root / "model_manifest.json"
    if manifest.is_file() and manifest.stat().st_size:
        try:
            data = json.loads(manifest.read_text())
        except json.JSONDecodeError:
            problems.append("model_manifest.json is not valid JSON")
        else:
            status = data.get("status")
            if expected_status and status != expected_status:
                problems.append(
                    f"model_manifest.json status is {status!r}, expected {expected_status!r}"
                )
    return problems


def command_fetch(args) -> None:
    out = _resolve(args.out)
    run_command(command_line(["kernels", "output", args.kernel, "-p", str(out), "-o"]))
    run_root = locate_run_root(out)
    problems = verify_run(run_root, expected_status=args.expect_status)
    if problems:
        print(f"Incomplete Kaggle run in {run_root}:", file=sys.stderr)
        for problem in problems:
            print(f"  - {problem}", file=sys.stderr)
        raise SystemExit(1)
    report_path = out / "fetch_report.json"
    report_path.write_text(
        json.dumps(
            {
                "kernel": args.kernel,
                "fetched_at": datetime.now(UTC).isoformat(),
                "run_dir": str(run_root),
                "artifacts": {
                    relative: sha256_file(run_root / relative)
                    for relative in REQUIRED_ARTIFACTS
                },
            },
            indent=2,
        )
    )
    print(f"Verified training evidence in {run_root}")
    print(f"Record: {report_path}")


def command_watch(args) -> None:
    command_status(args)
    command_fetch(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    dataset = subparsers.add_parser(
        "dataset", help="upload/refresh the PRIVATE reviewed-corpus dataset"
    )
    dataset.add_argument(
        "--dataset",
        required=True,
        type=parse_ref,
        help="<owner>/<slug> of the private Kaggle dataset",
    )
    dataset.add_argument(
        "--reviewed-dir",
        default="ml/data",
        help="directory holding reviewed_examples.jsonl",
    )
    dataset.add_argument(
        "--stage-dir",
        default="ml/runs/kaggle/dataset",
        help="upload folder (git-ignored)",
    )
    dataset.add_argument("--title", help="dataset title (6-50 characters)")
    dataset.add_argument(
        "--description",
        default="Human-reviewed VoxPrep HK corpus",
        help="dataset description shown on Kaggle",
    )
    dataset.add_argument("--notes", help="version notes for dataset version")
    dataset.add_argument(
        "--mode",
        choices=["auto", "create", "version"],
        default="auto",
        help="auto: create or version depending on whether the dataset exists",
    )
    dataset.add_argument(
        "--dry-run",
        action="store_true",
        help="stage files and print the command without uploading",
    )
    dataset.set_defaults(handler=command_dataset)

    push = subparsers.add_parser("push", help="push the private GPU kernel")
    push.add_argument(
        "--kernel",
        required=True,
        type=parse_ref,
        help="<owner>/<slug> of the private Kaggle kernel",
    )
    push.add_argument(
        "--dataset",
        action="append",
        type=parse_ref,
        default=[],
        help="private dataset to attach (repeatable)",
    )
    push.add_argument(
        "--model-source",
        action="append",
        default=[],
        type=validate_model_source,
        help="owner/slug/framework/instance/version Kaggle Model source",
    )
    push.add_argument(
        "--notebook",
        default=str(NOTEBOOK),
        help="notebook to push (copied, not edited)",
    )
    push.add_argument(
        "--stage-dir",
        default="ml/runs/kaggle/kernel",
        help="folder holding the notebook copy and kernel-metadata.json",
    )
    push.add_argument("--title", help="kernel title (>=5 characters)")
    push.add_argument(
        "--max-runtime-seconds",
        type=int,
        help="kaggle kernels push -t value (12h notebook maximum)",
    )
    push.add_argument("--accelerator", help="e.g. NvidiaTeslaT4 (default: image GPU)")
    push.add_argument("--machine-shape", help="optional machine_shape metadata value")
    push.add_argument(
        "--dry-run",
        action="store_true",
        help="write and print kernel-metadata.json without pushing",
    )
    push.set_defaults(handler=command_push)

    status = subparsers.add_parser("status", help="poll until COMPLETE/ERROR")
    status.add_argument(
        "--kernel", required=True, type=parse_ref, help="<owner>/<slug> to poll"
    )
    status.add_argument(
        "--timeout",
        type=float,
        default=21600.0,
        help="seconds to wait before giving up (default 6h)",
    )
    status.add_argument(
        "--interval",
        type=float,
        default=60.0,
        help="seconds between polls (default 60)",
    )
    status.set_defaults(handler=command_status)

    fetch = subparsers.add_parser("fetch", help="download and verify the run artefacts")
    fetch.add_argument(
        "--kernel", required=True, type=parse_ref, help="<owner>/<slug> to download"
    )
    fetch.add_argument(
        "--out",
        default="ml/runs/kaggle/output",
        help="local directory for the downloaded output",
    )
    fetch.add_argument(
        "--expect-status",
        default=COMPLETED_STATUS,
        help="required model_manifest.json status ('' to skip)",
    )
    fetch.set_defaults(handler=command_fetch)

    watch = subparsers.add_parser("watch", help="status then fetch")
    watch.add_argument(
        "--kernel", required=True, type=parse_ref, help="<owner>/<slug> to watch"
    )
    watch.add_argument(
        "--out",
        default="ml/runs/kaggle/output",
        help="local directory for the downloaded output",
    )
    watch.add_argument(
        "--timeout",
        type=float,
        default=21600.0,
        help="seconds to wait before giving up (default 6h)",
    )
    watch.add_argument(
        "--interval",
        type=float,
        default=60.0,
        help="seconds between polls (default 60)",
    )
    watch.add_argument(
        "--expect-status",
        default=COMPLETED_STATUS,
        help="required model_manifest.json status ('' to skip)",
    )
    watch.set_defaults(handler=command_watch)
    return parser


def format_ref(value) -> str:
    """Normalise an argparse-converted reference back to ``owner/slug``."""
    return f"{value[0]}/{value[1]}" if isinstance(value, tuple) else str(value)


def main(argv=None) -> None:
    args = build_parser().parse_args(argv)
    if args.command == "dataset":
        args.dataset = format_ref(args.dataset)
    else:
        args.kernel = format_ref(args.kernel)
        if args.command == "push":
            args.dataset = [format_ref(source) for source in args.dataset]
    try:
        args.handler(args)
    except subprocess.CalledProcessError as error:
        raise SystemExit(
            f"Command failed with exit {error.returncode}: "
            f"{shlex.join([str(part) for part in error.cmd])}"
        ) from error


if __name__ == "__main__":
    main()
