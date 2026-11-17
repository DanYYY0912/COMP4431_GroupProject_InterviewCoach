from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .providers import provider_url

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")

    database_url: str = f"sqlite:///{ROOT / 'data' / 'voxprep.db'}"
    model_provider: Literal["demo", "llama", "openai"] = "demo"
    llama_base_url: str = "http://127.0.0.1:8080/v1"
    model_name: str = "Qwen3-4B-Instruct-2507"
    agent_api_key: str = Field(default="", repr=False)
    model_timeout_seconds: float = 45
    report_timeout_seconds: float = 110
    whisper_base_url: str = "http://127.0.0.1:8081"
    asr_base_url: str = ""
    asr_model: str = ""
    asr_api_key: str = Field(default="", repr=False)
    embedding_base_url: str = ""
    embedding_model: str = "Qwen3-Embedding-0.6B"
    embedding_api_key: str = Field(default="", repr=False)
    embedding_dimensions: int = 1024
    reranker_base_url: str = ""
    reranker_model: str = "Qwen3-Reranker-0.6B"
    reranker_api_key: str = Field(default="", repr=False)
    inference_settings_path: Path = ROOT / "data" / "inference-settings.json"
    allowed_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:4431,http://127.0.0.1:4431"
    )
    evaluation_path: Path = ROOT / "evaluation" / "results" / "latest.json"
    frontend_dist: Path = ROOT / "frontend" / "dist"

    @field_validator(
        "llama_base_url",
        "whisper_base_url",
        "asr_base_url",
        "embedding_base_url",
        "reranker_base_url",
    )
    @classmethod
    def valid_model_services(cls, value: str) -> str:
        return provider_url(value)

    @property
    def origins(self) -> set[str]:
        return {x.strip() for x in self.allowed_origins.split(",") if x.strip()}
