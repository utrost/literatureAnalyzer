"""Cloud/provider routing in the analyzer's llm wrapper (no LLM deps needed)."""

import types

from lit_analyzer import llm
from lit_analyzer.config import ModelConfig


class _FakeMode:
    JSON = "JSON"
    TOOLS = "TOOLS"


_instructor = types.SimpleNamespace(Mode=_FakeMode)


def _cfg(**kw):
    base = dict(provider="ollama_chat", model="x")
    base.update(kw)
    return ModelConfig(**base)


def test_mode_json_for_local_and_openrouter():
    assert llm._instructor_mode(_instructor, _cfg(provider="ollama")) == "JSON"
    assert llm._instructor_mode(_instructor, _cfg(provider="openrouter")) == "JSON"


def test_mode_tools_for_openai_anthropic():
    assert llm._instructor_mode(_instructor, _cfg(provider="openai")) == "TOOLS"
    assert llm._instructor_mode(_instructor, _cfg(provider="anthropic")) == "TOOLS"


def test_json_mode_override():
    assert llm._instructor_mode(_instructor, _cfg(provider="openai", json_mode=True)) == "JSON"
    assert llm._instructor_mode(_instructor, _cfg(provider="openrouter", json_mode=False)) == "TOOLS"


def test_api_key_from_named_env(monkeypatch):
    monkeypatch.setenv("LIT_ROUTER_KEY", "sk-xyz")
    cfg = _cfg(provider="openrouter", model="m", api_key_env="LIT_ROUTER_KEY")
    assert llm._extra_kwargs(cfg)["api_key"] == "sk-xyz"


def test_no_api_key_without_env(monkeypatch):
    monkeypatch.delenv("NOPE", raising=False)
    assert "api_key" not in llm._extra_kwargs(_cfg(provider="openrouter", model="m", api_key_env="NOPE"))


def test_model_id_prefixes_provider():
    assert llm._model_id(_cfg(provider="openrouter", model="a/b")) == "openrouter/a/b"
    assert llm._model_id(_cfg(provider="ollama", model="q")) == "ollama_chat/q"
