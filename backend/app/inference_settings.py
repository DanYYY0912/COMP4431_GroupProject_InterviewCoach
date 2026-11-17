"""Persist server-side credentials and publish immutable runtime snapshots."""

import json
import os
import tempfile
from contextlib import contextmanager, suppress
from typing import Literal

import httpx
from fastapi import HTTPException
from pydantic import Field, SecretStr, field_validator, model_validator

from .config import Settings
from .providers import bearer_headers, provider_url
from .schemas import StrictModel

ComponentName = Literal["agent", "asr", "embedding", "reranker"]
COMPONENTS = ("agent", "asr", "embedding", "reranker")


class DiscoveryInput(StrictModel):
    base_url: str = Field(max_length=2048)
    model: str = Field(default="", max_length=256)
    api_key: SecretStr | None

    _url = field_validator("base_url")(provider_url)

    @field_validator("model")
    @classmethod
    def model_label(cls, value):
        if any(ord(c) < 32 for c in value):
            raise ValueError("Model identifiers cannot contain control characters.")
        return value.strip()

    @field_validator("api_key")
    @classmethod
    def valid_key(cls, value):
        if value is not None:
            raw = value.get_secret_value()
            if len(raw) > 4096 or any(ord(c) < 33 or ord(c) > 126 for c in raw):
                raise ValueError(
                    "API keys must be at most 4096 printable ASCII characters without whitespace."
                )
        return value


class ComponentInput(DiscoveryInput):
    model: str = Field(max_length=256)

    @model_validator(mode="after")
    def complete_destination(self):
        if bool(self.base_url) != bool(self.model):
            raise ValueError("Set both base URL and model, or clear both to disable the override.")
        if not self.base_url and self.api_key and self.api_key.get_secret_value():
            raise ValueError("Clear the API key when disabling an override.")
        return self


class InferenceInput(StrictModel):
    agent: ComponentInput
    asr: ComponentInput
    embedding: ComponentInput
    reranker: ComponentInput


class ComponentView(StrictModel):
    base_url: str
    model: str
    api_key_set: bool


class InferenceView(StrictModel):
    agent: ComponentView
    asr: ComponentView
    embedding: ComponentView
    reranker: ComponentView


class ModelsView(StrictModel):
    models: list[str]


class InferenceSettings:
    def __init__(self, settings: Settings):
        self.current = settings
        self.path = settings.inference_settings_path
        self.active_operations = 0
        self.records = self._defaults(settings)
        if self.path.exists():
            try:
                if self.path.stat().st_size > 64 * 1024:
                    raise ValueError()
                data = InferenceInput.model_validate_json(self.path.read_text())
                if any(getattr(data, name).api_key is None for name in COMPONENTS):
                    raise ValueError()
                self.records = self.prepare(data)
                self.current = self.snapshot(self.records)
            except (ValueError, OSError):
                raise RuntimeError(
                    "Inference settings could not be loaded. Check the settings file format and permissions."
                ) from None

    @staticmethod
    def _defaults(settings):
        result = {}
        for name in COMPONENTS:
            url = (
                settings.llama_base_url
                if name == "agent"
                else getattr(settings, f"{name}_base_url")
            )
            model = settings.model_name if name == "agent" else getattr(settings, f"{name}_model")
            if name == "agent" and settings.model_provider == "demo":
                url = ""
            result[name] = {
                "base_url": url,
                "model": model if url else "",
                "api_key": getattr(settings, f"{name}_api_key") if url else "",
            }
        return result

    @contextmanager
    def operation(self):
        self.active_operations += 1
        try:
            yield self.current
        finally:
            self.active_operations -= 1

    def public(self) -> InferenceView:
        return InferenceView.model_validate(
            {
                name: {
                    "base_url": item["base_url"],
                    "model": item["model"],
                    "api_key_set": bool(item["api_key"]),
                }
                for name, item in self.records.items()
            }
        )

    def resolve_key(self, name: str, value: DiscoveryInput) -> str:
        if value.api_key is not None:
            return value.api_key.get_secret_value()
        previous = self.records[name]
        if previous["base_url"] != value.base_url:
            raise HTTPException(
                422, "The destination changed. Explicitly clear the API key or provide a new key."
            )
        return previous["api_key"]

    def prepare(self, data: InferenceInput) -> dict:
        if self.active_operations:
            raise HTTPException(
                409, "Inference is in progress. Wait for it to finish before saving settings."
            )
        return {
            name: {
                "base_url": getattr(data, name).base_url,
                "model": getattr(data, name).model,
                "api_key": self.resolve_key(name, getattr(data, name)),
            }
            for name in COMPONENTS
        }

    def snapshot(self, records: dict) -> Settings:
        values = {}
        for name, item in records.items():
            values["llama_base_url" if name == "agent" else f"{name}_base_url"] = item["base_url"]
            values["model_name" if name == "agent" else f"{name}_model"] = item["model"]
            values[f"{name}_api_key"] = item["api_key"]
        values["model_provider"] = "openai" if records["agent"]["base_url"] else "demo"
        return self.current.model_copy(update=values)

    def save(self, records: dict):
        temporary = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary = tempfile.mkstemp(
                prefix=".inference-settings-", dir=self.path.parent
            )
            with os.fdopen(descriptor, "w") as output:
                os.fchmod(output.fileno(), 0o600)
                json.dump(records, output, ensure_ascii=False)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, self.path)
        except OSError:
            raise HTTPException(
                503, "Settings could not be saved. Check local storage permissions and retry."
            ) from None
        finally:
            if temporary and os.path.exists(temporary):
                with suppress(OSError):
                    os.unlink(temporary)
        self.current = self.snapshot(records)
        self.records = records

    async def models(self, name: ComponentName, data: DiscoveryInput) -> ModelsView:
        key = self.resolve_key(name, data)
        if not data.base_url:
            raise HTTPException(422, "Enter a base URL before loading models.")
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
                response = await client.get(f"{data.base_url}/models", headers=bearer_headers(key))
                response.raise_for_status()
                raw = response.json()["data"]
            if not isinstance(raw, list) or len(raw) > 5000:
                raise ValueError()
            ids = [item["id"] for item in raw]
            if any(
                not isinstance(item, str)
                or not item
                or len(item) > 256
                or any(ord(c) < 32 for c in item)
                for item in ids
            ):
                raise ValueError()
            return ModelsView(models=sorted(set(ids)))
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            raise HTTPException(
                502,
                "Could not load models. Check the base URL, API key, and provider availability.",
            ) from None


def load_saved_inference(settings: Settings) -> Settings:
    """Read effective inference configuration without changing files or starting services."""
    return InferenceSettings(settings).current
