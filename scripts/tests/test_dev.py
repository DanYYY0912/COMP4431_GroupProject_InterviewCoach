"""Launcher checks do not start or stop real services."""

import io
import json

import pytest

from scripts import dev


def test_model_command_preserves_base_flags_and_supports_relative_or_absolute_lora(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(dev, "ROOT", tmp_path)
    monkeypatch.setattr(dev, "ENV", {})
    base = tmp_path / "base.gguf"
    command = dev.llama_command(base)
    assert command == [
        "llama-server",
        "-m",
        base,
        "--host",
        "127.0.0.1",
        "--port",
        "8080",
        "-c",
        "8192",
        "-ngl",
        "99",
        "--jinja",
        "--parallel",
        "1",
    ]
    adapter = tmp_path / "adapter.gguf"
    adapter.touch()
    for value in ("adapter.gguf", str(adapter)):
        monkeypatch.setitem(dev.ENV, "LORA_PATH", value)
        assert dev.llama_command(base) == [*command, "--lora", adapter]
    monkeypatch.setitem(dev.ENV, "LORA_PATH", "missing.gguf")
    with pytest.raises(SystemExit, match="does not exist"):
        dev.llama_command(base)


def test_existing_model_service_must_have_requested_adapter_active(
    tmp_path, monkeypatch
):
    adapter = tmp_path / "adapter.gguf"
    adapter.touch()
    monkeypatch.setattr(dev, "ROOT", tmp_path)
    monkeypatch.setattr(dev, "ENV", {"LORA_PATH": "adapter.gguf"})
    for adapters, valid in (
        ([{"path": str(adapter), "scale": 1}], True),
        ([], False),
        ([{"path": str(adapter), "scale": 0}], False),
    ):
        monkeypatch.setattr(
            dev.urllib.request,
            "urlopen",
            lambda *a, adapters=adapters, **kw: io.BytesIO(
                json.dumps(adapters).encode()
            ),
        )
        if valid:
            dev.check_running_adapter()
        else:
            with pytest.raises(SystemExit, match="does not have"):
                dev.check_running_adapter()


def test_demo_start_ignores_lora_and_does_not_launch_native_models(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(dev, "ROOT", tmp_path)
    monkeypatch.setattr(
        dev,
        "ENV",
        {"MODEL_PROVIDER": "demo", "VOXPREP_SQLITE": "1", "LORA_PATH": "missing.gguf"},
    )
    monkeypatch.setattr(dev, "load_env", lambda: None)
    monkeypatch.setattr(dev, "pnpm", lambda: "pnpm-test")
    monkeypatch.setattr(dev.signal, "signal", lambda *a: None)
    commands = []
    monkeypatch.setattr(dev, "run", lambda args, **kw: commands.append(args))

    class FakeChild:
        def poll(self):
            return None

        def terminate(self):
            pass

        def wait(self, **kwargs):
            return 0

    def start(command, **kwargs):
        commands.append(command)
        return FakeChild()

    monkeypatch.setattr(dev.subprocess, "Popen", start)
    monkeypatch.setattr(
        dev.time, "sleep", lambda *a: (_ for _ in ()).throw(KeyboardInterrupt())
    )
    dev.serve("dev")
    assert any("uvicorn" in command for command in commands)
    assert not any(
        "llama-server" in command or "whisper-server" in command for command in commands
    )
