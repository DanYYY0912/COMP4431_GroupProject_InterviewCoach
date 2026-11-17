"""Saved remote providers must not start unused native inference processes."""

import json

import pytest

from scripts import dev


def test_saved_external_settings_skip_native_models_even_when_weights_exist(
    tmp_path, monkeypatch
):
    models = tmp_path / "models"
    models.mkdir()
    for name in [
        "Qwen3-4B-Instruct-2507-Q4_K_M.gguf",
        "Qwen3-Embedding-0.6B-Q8_0.gguf",
        "Qwen3-Reranker-0.6B-Q8_0.gguf",
        "ggml-large-v3-turbo-q5_0.bin",
    ]:
        (models / name).touch()
    saved = tmp_path / "inference-settings.json"
    saved.write_text(
        json.dumps(
            {
                name: {
                    "base_url": f"https://provider.example/{name}/v1",
                    "model": name,
                    "api_key": "",
                }
                for name in ("agent", "asr", "embedding", "reranker")
            }
        )
    )
    monkeypatch.setattr(dev, "ROOT", tmp_path)
    monkeypatch.setattr(
        dev,
        "ENV",
        {
            "VOXPREP_SQLITE": "1",
            "INFERENCE_SETTINGS_PATH": str(saved),
        },
    )
    monkeypatch.setattr(dev, "run", lambda *args, **kwargs: None)
    monkeypatch.setattr(dev, "pnpm", lambda: "pnpm")
    monkeypatch.setattr(dev.signal, "signal", lambda *args: None)
    started = []

    class CompletedProcess:
        def __init__(self, command, **kwargs):
            started.append(command)

        def poll(self):
            return 0

        def wait(self, timeout):
            return 0

    monkeypatch.setattr(dev.subprocess, "Popen", CompletedProcess)
    # No remote /health assumption or native readiness wait is appropriate here.
    monkeypatch.setattr(
        dev, "available", lambda url: pytest.fail("Unexpected native probe")
    )
    with pytest.raises(RuntimeError, match="service exited"):
        dev.serve("demo")
    assert len(started) == 1
    assert started[0][1:3] == ["-m", "uvicorn"]
    assert started[0][started[0].index("--port") + 1] == "4431"
