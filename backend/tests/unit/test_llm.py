"""Unit tests for the provider-agnostic LLM client and fallback chain."""

import pytest
from src.core import llm


def test_enabled_providers_filters_and_orders(monkeypatch):
    monkeypatch.setattr(llm.settings, "OPENROUTER_API_KEY", "k-or")
    monkeypatch.setattr(llm.settings, "GROQ_API_KEY", "k-groq")
    monkeypatch.setattr(llm.settings, "GEMINI_API_KEY", None)
    monkeypatch.setattr(llm.settings, "LLM_PROVIDER_ORDER", "groq,openrouter,gemini")

    providers = llm.enabled_providers()
    assert [p.name for p in providers] == ["groq", "openrouter"]  # gemini skipped (no key)


def test_extract_json_tolerates_fences_and_prose():
    assert llm._extract_json('{"a": 1}') == {"a": 1}
    assert llm._extract_json('```json\n{"a": 2}\n```') == {"a": 2}
    assert llm._extract_json("Sure! Here you go: {\"a\": 3} hope that helps") == {"a": 3}
    assert llm._extract_json("no json here") is None


@pytest.mark.asyncio
async def test_complete_json_disabled_returns_none(monkeypatch):
    monkeypatch.setattr(llm.settings, "LLM_ENABLED", False)
    assert await llm.complete_json("sys", "user") is None


@pytest.mark.asyncio
async def test_complete_json_falls_back_to_next_provider(monkeypatch):
    monkeypatch.setattr(llm.settings, "LLM_ENABLED", True)
    monkeypatch.setattr(llm.settings, "OPENROUTER_API_KEY", "k1")
    monkeypatch.setattr(llm.settings, "GROQ_API_KEY", "k2")
    monkeypatch.setattr(llm.settings, "GEMINI_API_KEY", None)
    monkeypatch.setattr(llm.settings, "LLM_PROVIDER_ORDER", "openrouter,groq,gemini")

    calls: list[str] = []

    async def fake_call(provider, system, user):
        calls.append(provider.name)
        if provider.name == "openrouter":
            raise RuntimeError("429 rate limited")
        return {"result": "ok", "via": provider.name}

    monkeypatch.setattr(llm, "_call_provider", fake_call)

    result = await llm.complete_json("sys", "user")
    assert result == {"result": "ok", "via": "groq"}
    assert calls == ["openrouter", "groq"]  # tried first, fell back to second


@pytest.mark.asyncio
async def test_complete_json_returns_none_when_all_fail(monkeypatch):
    monkeypatch.setattr(llm.settings, "LLM_ENABLED", True)
    monkeypatch.setattr(llm.settings, "OPENROUTER_API_KEY", "k1")
    monkeypatch.setattr(llm.settings, "GROQ_API_KEY", "k2")
    monkeypatch.setattr(llm.settings, "GEMINI_API_KEY", None)

    async def always_fail(provider, system, user):
        raise RuntimeError("boom")

    monkeypatch.setattr(llm, "_call_provider", always_fail)
    assert await llm.complete_json("sys", "user") is None
