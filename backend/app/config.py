from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    database_url: str = f"sqlite:///{ROOT / 'data' / 'voxprep.db'}"
    model_provider: Literal["demo", "llama"] = "demo"
    llama_base_url: str = "http://127.0.0.1:8080/v1"
    model_name: str = "Qwen3-4B-Instruct-2507"
    model_timeout_seconds: float = 45
    report_timeout_seconds: float = 110
    azure_speech_key: str = ""
    azure_speech_region: str = ""
    whisper_base_url: str = "http://127.0.0.1:8081"
    embedding_base_url: str = ""
    embedding_model: str = "Qwen3-Embedding-0.6B"
    embedding_dimensions: int = 1024
    reranker_base_url: str = ""
    reranker_model: str = "Qwen3-Reranker-0.6B"
    allowed_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000"
    )
    evaluation_path: Path = ROOT / "evaluation" / "results" / "latest.json"
    frontend_dist: Path = ROOT / "frontend" / "dist"

    @field_validator(
        "llama_base_url", "whisper_base_url", "embedding_base_url", "reranker_base_url"
    )
    @classmethod
    def only_local_model_services(cls, value: str) -> str:
        if not value:
            return value
        parsed = urlparse(value)
        if (
            parsed.scheme not in {"http", "https"}
            or parsed.hostname
            not in {
                "localhost",
                "127.0.0.1",
                "::1",
                "host.docker.internal",
                "llama",
                "whisper",
            }
            or parsed.username
            or parsed.password
        ):
            raise ValueError("Model services must use a local host; transcripts must remain local.")
        return value.rstrip("/")

    @field_validator("azure_speech_region")
    @classmethod
    def region_is_safe(cls, value: str) -> str:
        if value and (not value.isalnum() or len(value) > 40):
            raise ValueError("Invalid Azure region")
        return value

    @property
    def origins(self) -> set[str]:
        return {x.strip() for x in self.allowed_origins.split(",") if x.strip()}
