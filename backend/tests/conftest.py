"""Keep deterministic tests independent of the operator's model and speech settings."""

import pytest

from app.config import Settings


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch):
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    for field in Settings.model_fields:
        monkeypatch.delenv(field.upper(), raising=False)
