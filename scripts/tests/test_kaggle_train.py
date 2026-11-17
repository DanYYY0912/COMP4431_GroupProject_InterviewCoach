"""The Kaggle path is tested without a network, a token or a GPU."""

import argparse
import json
import subprocess
import zipfile

import pytest

from scripts import kaggle_train as kt

REAL_KAGGLE_CLI = kt.kaggle_cli
KERNEL = "kelvin0611/voxprep-qlora"
DATASET = "kelvin0611/voxprep-hk-reviewed"


@pytest.fixture(autouse=True)
def fixed_cli(monkeypatch):
    """Never resolve a real Kaggle binary during tests."""
    monkeypatch.setattr(kt, "kaggle_cli", lambda environ=None: ["kaggle"])


def write_run(root, *, status="training_completed", artifacts=kt.REQUIRED_ARTIFACTS):
    root.mkdir(parents=True, exist_ok=True)
    for relative in artifacts:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x")
    (root / "model_manifest.json").write_text(json.dumps({"status": status}))
    return root


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def statuses(*values):
    pending = iter(values)
    return lambda: f'{KERNEL} has status "{next(pending)}"'


def test_kernel_metadata_is_private_gpu_and_internet_with_sources():
    meta = kt.kernel_metadata(
        slug=KERNEL,
        title="Voxprep Qlora",
        code_file="VoxPrep_QLoRA.ipynb",
        dataset_sources=[DATASET],
        model_sources=["qwen-lm/qwen3/transformers/4b/1"],
    )
    assert meta["id"] == KERNEL
    assert meta["is_private"] is True
    assert meta["enable_gpu"] is True
    assert meta["enable_internet"] is True
    assert meta["enable_tpu"] is False
    assert meta["dataset_sources"] == [DATASET]
    assert meta["model_sources"] == ["qwen-lm/qwen3/transformers/4b/1"]
    assert meta["code_file"] == "VoxPrep_QLoRA.ipynb"
    assert "machine_shape" not in meta
    assert (
        kt.kernel_metadata(
            slug=KERNEL,
            title="Voxprep Qlora",
            code_file="n.ipynb",
            machine_shape="NvidiaTeslaT4",
        )["machine_shape"]
        == "NvidiaTeslaT4"
    )


def test_kernel_titles_keep_the_slug_characters():
    title = kt.title_for_slug("voxprep-qlora")
    assert title == "VoxPrep QLoRA"
    assert title.lower().replace(" ", "-") == "voxprep-qlora"
    assert len(kt.title_for_slug("ab")) >= 5


def test_push_dry_run_writes_private_metadata_and_runs_nothing(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(kt, "ROOT", tmp_path)
    notebook = tmp_path / "ml/VoxPrep_QLoRA.ipynb"
    notebook.parent.mkdir(parents=True)
    notebook.write_text("{}")
    calls = []
    monkeypatch.setattr(kt.subprocess, "run", lambda *a, **kw: calls.append(a))

    kt.main(["push", "--kernel", KERNEL, "--dataset", DATASET, "--dry-run"])

    assert calls == []
    stage = tmp_path / "ml/runs/kaggle/kernel"
    meta = json.loads((stage / "kernel-metadata.json").read_text())
    assert meta["is_private"] is True
    assert meta["enable_gpu"] is True
    assert meta["enable_internet"] is True
    assert meta["dataset_sources"] == [DATASET]
    assert (stage / "VoxPrep_QLoRA.ipynb").read_text() == "{}"
    printed = capsys.readouterr().out
    assert "+ kaggle kernels push -p" in printed
    assert "Dry run: nothing pushed." in printed


def test_dataset_upload_is_never_public_and_versions_existing_datasets():
    create = kt.dataset_upload_command("/stage", exists=False)
    assert create[:3] == ["kaggle", "datasets", "create"]
    assert "--dir-mode" in create and "zip" in create
    assert "--public" not in create and "-u" not in create

    version = kt.dataset_upload_command("/stage", exists=True, notes="refresh")
    assert version[:3] == ["kaggle", "datasets", "version"]
    assert version[-2:] == ["-m", "refresh"]
    assert "--public" not in version and "-u" not in version


def test_is_private_requires_the_explicit_kaggle_flag():
    assert kt.is_private(json.dumps({"info": {"isPrivate": True}})) is True
    assert kt.is_private(json.dumps({"info": {"title": "VoxPrep"}})) is False
    assert kt.is_private(json.dumps({"info": {"isPrivate": False}})) is False


def test_dataset_dry_run_stages_corpus_and_prints_the_upload(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(kt, "ROOT", tmp_path)
    source = tmp_path / "ml/data"
    source.mkdir(parents=True)
    rid = '{"id": "row-1"}\n{"id": "row-2"}\n'
    (source / "reviewed_examples.jsonl").write_text(rid)
    (source / "split_manifest.json").write_text("{}")
    (tmp_path / "ml/config.json").write_text(json.dumps({"expected_examples": 2}))
    calls = []
    monkeypatch.setattr(kt.subprocess, "run", lambda *a, **kw: calls.append(a))

    kt.main(["dataset", "--dataset", DATASET, "--mode", "create", "--dry-run"])

    assert calls == []
    stage = tmp_path / "ml/runs/kaggle/dataset"
    manifest = json.loads((stage / "dataset_manifest.json").read_text())
    assert manifest["rows"] == 2
    assert manifest["files"]["reviewed_examples.jsonl"]["sha256"] == kt.sha256_file(
        source / "reviewed_examples.jsonl"
    )
    assert (stage / "split_manifest.json").is_file()
    meta = json.loads((stage / "dataset-metadata.json").read_text())
    assert meta["id"] == DATASET
    assert len(meta["licenses"]) == 1
    printed = capsys.readouterr().out
    assert "+ kaggle datasets create" in printed
    assert DATASET in printed


def test_dataset_refuses_to_stage_without_a_reviewed_corpus(tmp_path, monkeypatch):
    monkeypatch.setattr(kt, "ROOT", tmp_path)
    with pytest.raises(SystemExit, match="not found"):
        kt.main(["dataset", "--dataset", DATASET, "--dry-run"])


def test_restaging_drops_stale_files_from_the_upload_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(kt, "ROOT", tmp_path)
    source = tmp_path / "ml/data"
    source.mkdir(parents=True)
    (source / "reviewed_examples.jsonl").write_text('{"id": "row-1"}\n')
    stage = tmp_path / "ml/runs/kaggle/dataset"
    command = ["dataset", "--dataset", DATASET, "--mode", "create", "--dry-run"]
    kt.main(command)
    (stage / "stale.jsonl").write_text("{}\n")
    kt.main(command)

    assert not (stage / "stale.jsonl").exists()
    manifest = json.loads((stage / "dataset_manifest.json").read_text())
    assert set(manifest["files"]) == {"reviewed_examples.jsonl"}


def test_stage_dir_may_not_be_the_corpus_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(kt, "ROOT", tmp_path)
    source = tmp_path / "ml/data"
    source.mkdir(parents=True)
    (source / "reviewed_examples.jsonl").write_text("{}\n")

    with pytest.raises(SystemExit, match="must not be the corpus directory"):
        kt.main(
            [
                "dataset",
                "--dataset",
                DATASET,
                "--stage-dir",
                str(source),
                "--dry-run",
            ]
        )
    assert (source / "reviewed_examples.jsonl").is_file()


def test_push_requires_the_notebook(tmp_path, monkeypatch):
    monkeypatch.setattr(kt, "ROOT", tmp_path)
    with pytest.raises(SystemExit, match="Notebook not found"):
        kt.main(["push", "--kernel", KERNEL, "--dry-run"])


def test_poll_returns_when_the_kernel_completes(capsys):
    clock = FakeClock()
    result = kt.poll_until_done(
        statuses("QUEUED", "RUNNING", "COMPLETE"),
        timeout=3600,
        interval=60,
        sleep=clock.sleep,
        clock=clock,
    )
    assert result == "COMPLETE"
    assert "[120s] COMPLETE" in capsys.readouterr().out


def test_poll_stops_on_a_failed_kernel():
    clock = FakeClock()
    with pytest.raises(SystemExit, match="failed with status ERROR"):
        kt.poll_until_done(
            statuses("QUEUED", "ERROR"),
            timeout=3600,
            interval=60,
            sleep=clock.sleep,
            clock=clock,
        )


def test_poll_times_out_while_still_queued():
    clock = FakeClock()
    with pytest.raises(SystemExit, match="Timed out after 120s"):
        kt.poll_until_done(
            lambda: f'{KERNEL} has status "QUEUED"',
            timeout=120,
            interval=60,
            sleep=clock.sleep,
            clock=clock,
        )


def test_status_parse_keeps_the_failure_message():
    status, message = kt.parse_status(
        f'{KERNEL} has status "ERROR"\nFailure message: "CUDA out of memory"'
    )
    assert (status, message) == ("ERROR", "CUDA out of memory")


def test_status_parse_rejects_unexpected_output():
    with pytest.raises(SystemExit, match="Unexpected"):
        kt.parse_status("404 Not Found")


def test_status_explains_a_failed_status_call(monkeypatch):
    def boom(command, **kwargs):
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(kt, "run_command", boom)
    with pytest.raises(SystemExit, match="Check the owner/slug"):
        kt.main(["status", "--kernel", KERNEL])


def test_main_reports_a_failed_kaggle_command(tmp_path, monkeypatch):
    monkeypatch.setattr(kt, "ROOT", tmp_path)
    notebook = tmp_path / "ml/VoxPrep_QLoRA.ipynb"
    notebook.parent.mkdir(parents=True)
    notebook.write_text("{}")

    def boom(command, **kwargs):
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(kt, "run_command", boom)
    with pytest.raises(SystemExit, match="Command failed with exit 1"):
        kt.main(["push", "--kernel", KERNEL])


def test_missing_adapter_makes_fetch_fail_with_a_non_zero_exit(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.setattr(kt, "ROOT", tmp_path)
    monkeypatch.setattr(kt, "run_command", lambda command, **kw: "")
    run = tmp_path / "out/voxprep-qlora"
    write_run(
        run,
        artifacts=("loss.png", "training_log.jsonl", "model_manifest.json"),
    )

    with pytest.raises(SystemExit) as exit_info:
        kt.main(["fetch", "--kernel", KERNEL, "--out", "out"])

    assert exit_info.value.code == 1
    stderr = capsys.readouterr().err
    assert "missing adapter/adapter_model.safetensors" in stderr


def test_fetch_writes_a_report_when_every_artifact_is_present(tmp_path, monkeypatch):
    monkeypatch.setattr(kt, "ROOT", tmp_path)
    monkeypatch.setattr(kt, "run_command", lambda command, **kw: "")
    write_run(tmp_path / "out/voxprep-qlora")

    kt.main(["fetch", "--kernel", KERNEL, "--out", "out"])

    report = json.loads((tmp_path / "out/fetch_report.json").read_text())
    assert report["kernel"] == KERNEL
    assert set(report["artifacts"]) == set(kt.REQUIRED_ARTIFACTS)


def test_verify_run_rejects_an_unfinished_manifest(tmp_path):
    run = write_run(tmp_path / "run", status="training_queued")
    problems = kt.verify_run(run)
    assert problems == [
        (
            "model_manifest.json status is 'training_queued', "
            "expected 'training_completed'"
        )
    ]


def test_verify_run_flags_empty_artifacts(tmp_path):
    run = write_run(tmp_path / "run")
    (run / "loss.png").write_text("")
    assert kt.verify_run(run) == ["empty loss.png"]


def test_locate_run_root_unpacks_the_evidence_zip(tmp_path):
    archive = tmp_path / "voxprep-training-evidence.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("model_manifest.json", "{}")

    assert kt.locate_run_root(tmp_path).name == "voxprep-training-evidence"
    assert (tmp_path / "_unpacked").is_dir()


def test_locate_run_root_prefers_the_named_run_directory(tmp_path):
    write_run(tmp_path / "COMP4431/ml/runs/voxprep-qlora")
    write_run(tmp_path / "stray")
    assert kt.locate_run_root(tmp_path).name == "voxprep-qlora"


def test_locate_run_root_fails_loudly_without_a_manifest(tmp_path):
    with pytest.raises(SystemExit, match="No model_manifest.json"):
        kt.locate_run_root(tmp_path)


@pytest.mark.parametrize(
    "value",
    ["voxprep-qlora", "kelvin0611/VoxPrep", "a/b", "kelvin0611/voxprep_qlora"],
)
def test_references_must_be_lowercase_owner_slash_slug(value):
    with pytest.raises(argparse.ArgumentTypeError):
        kt.parse_ref(value)


def test_cli_rejects_an_unqualified_kernel_reference(capsys):
    with pytest.raises(SystemExit) as exit_info:
        kt.main(["fetch", "--kernel", "voxprep-qlora"])
    assert exit_info.value.code == 2
    assert "<owner>/<slug>" in capsys.readouterr().err


def test_model_sources_need_five_segments():
    with pytest.raises(argparse.ArgumentTypeError):
        kt.validate_model_source("qwen-lm/qwen3")
    value = "qwen-lm/qwen3/transformers/4b/1"
    assert kt.validate_model_source(value) == value


def test_kaggle_cli_honours_the_environment_override():
    command = REAL_KAGGLE_CLI({"KAGGLE_CLI": "uv tool run --from kaggle kaggle"})
    assert command == ["uv", "tool", "run", "--from", "kaggle", "kaggle"]


def test_command_line_prefixes_the_resolved_cli():
    assert kt.command_line(["kernels", "status", KERNEL]) == [
        "kaggle",
        "kernels",
        "status",
        KERNEL,
    ]
