"""Config loader — mirrors Endless's YAML→Pydantic shape.

Only the deep (LLM) passes need config; the deterministic core takes none. A
config file is therefore optional and only consulted for ``--deep``.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field


class ModelConfig(BaseModel):
    provider: str
    model: str
    endpoint: str | None = None
    api_key_env: str | None = Field(
        default=None,
        description=(
            "Name of the env var holding this provider's API key (e.g. "
            "OPENROUTER_API_KEY). Optional — LiteLLM reads the standard provider "
            "vars automatically. Put the NAME here, never the key (secrets go in .env)."
        ),
    )
    json_mode: bool | None = Field(
        default=None,
        description=(
            "Structured-output mode. None = auto (JSON for Ollama/OpenRouter, "
            "tool-calls for OpenAI/Anthropic). Force true for a hosted model that "
            "doesn't support OpenAI-style tool calls."
        ),
    )
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    max_tokens: int | None = None
    thinking: bool = True


class DeepConfig(BaseModel):
    """Models for the LLM-powered extraction roles."""

    lector: ModelConfig
    beat_labeler: ModelConfig
    classifier: ModelConfig


class Config(BaseModel):
    deep: DeepConfig


def default_config_path() -> Path:
    for name in ("config.yaml", "config.example.yaml"):
        p = Path(name)
        if p.exists():
            return p
    return Path("config.yaml")


def load_config(path: str | Path) -> Config:
    raw = yaml.safe_load(Path(path).read_text())
    return Config.model_validate(raw)
