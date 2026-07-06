"""Slim LLM wrapper for the extraction roles.

Deliberately thinner than Endless's llm.py — this tool only makes structured
calls, never free prose. litellm/instructor are imported lazily so the base
package (deterministic core) installs and tests with no LLM dependency. Install
them with ``uv sync --extra deep``.

The Ollama provider normalization and JSON-mode handling are carried over from
Endless verbatim because the same pitfalls apply (Appendix C): plain ``ollama``
skips chat templates, and local models need ``Mode.JSON`` not ``Mode.TOOLS``.
"""

from __future__ import annotations

from importlib import resources
from typing import TypeVar

from pydantic import BaseModel

from .config import ModelConfig

T = TypeVar("T", bound=BaseModel)


class DeepDependencyError(RuntimeError):
    """Raised when a --deep pass is requested but LLM deps aren't installed."""


def _require_deep_deps():
    try:
        import instructor  # noqa: F401
        import litellm  # noqa: F401
    except ImportError as exc:  # pragma: no cover - exercised only without extra
        raise DeepDependencyError(
            "The --deep passes need the 'deep' extra. Install it with "
            "`uv sync --extra deep` (adds litellm + instructor)."
        ) from exc
    return instructor, litellm


def _normalize_provider(provider: str) -> str:
    # ollama's /api/generate skips chat templates; ollama_chat (/api/chat) is
    # reliable. Same fix as Endless (design doc Appendix C, pitfall 2).
    return "ollama_chat" if provider == "ollama" else provider


def _model_id(cfg: ModelConfig) -> str:
    return f"{_normalize_provider(cfg.provider)}/{cfg.model}"


def _extra_kwargs(cfg: ModelConfig) -> dict:
    kwargs: dict = {"temperature": cfg.temperature}
    if cfg.endpoint:
        kwargs["api_base"] = cfg.endpoint
    if cfg.max_tokens is not None:
        kwargs["max_tokens"] = cfg.max_tokens
    normalized = _normalize_provider(cfg.provider)
    if normalized.startswith("ollama"):
        kwargs["format"] = "json"
        if not cfg.thinking:
            kwargs["think"] = False
    return kwargs


def load_prompt(name: str) -> str:
    return resources.files("lit_analyzer.prompts").joinpath(name).read_text()


def call_structured(
    cfg: ModelConfig,
    *,
    system: str,
    user: str,
    response_model: type[T],
    max_retries: int = 3,
) -> T:
    """Call an LLM and validate output against a Pydantic model."""
    instructor, litellm = _require_deep_deps()
    mode = (
        instructor.Mode.JSON
        if _normalize_provider(cfg.provider).startswith("ollama")
        else instructor.Mode.TOOLS
    )
    client = instructor.from_litellm(litellm.completion, mode=mode)
    return client.create(
        model=_model_id(cfg),
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_model=response_model,
        max_retries=max_retries,
        **_extra_kwargs(cfg),
    )
