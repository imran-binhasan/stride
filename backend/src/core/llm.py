"""Provider-agnostic LLM client with a free-tier fallback chain.

Every configured provider speaks the OpenAI-compatible ``/chat/completions`` API, so any
free key (OpenRouter, Groq, Gemini's OpenAI endpoint, ...) plugs in. Providers are tried in
``LLM_PROVIDER_ORDER``; the first that responds wins, and if all fail the caller falls back
to a deterministic heuristic. Free tiers may train on prompts — do not send sensitive data
to a free provider in production.
"""

import json
import logging
import re
from dataclasses import dataclass

import httpx
from src.config import settings

logger = logging.getLogger("a3zen.llm")

# name -> (base_url, settings key attr, settings model attr)
_PROVIDER_SPECS: dict[str, tuple[str, str, str]] = {
    "openrouter": ("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY", "OPENROUTER_MODEL"),
    "groq": ("https://api.groq.com/openai/v1", "GROQ_API_KEY", "GROQ_MODEL"),
    "gemini": (
        "https://generativelanguage.googleapis.com/v1beta/openai",
        "GEMINI_API_KEY",
        "GEMINI_MODEL",
    ),
}


@dataclass(frozen=True)
class LLMProvider:
    name: str
    base_url: str
    api_key: str
    model: str


def enabled_providers() -> list[LLMProvider]:
    """Build the ordered list of providers that have an API key configured."""
    providers: list[LLMProvider] = []
    for name in (p.strip() for p in settings.LLM_PROVIDER_ORDER.split(",")):
        spec = _PROVIDER_SPECS.get(name)
        if not spec:
            continue
        base_url, key_attr, model_attr = spec
        api_key = getattr(settings, key_attr, None)
        if api_key:
            providers.append(
                LLMProvider(name, base_url, api_key, getattr(settings, model_attr))
            )
    return providers


def _extract_json(content: str) -> dict | None:
    """Parse a JSON object from a model response, tolerating markdown fences / prose."""
    try:
        return json.loads(content)
    except (ValueError, TypeError):
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except (ValueError, TypeError):
            return None


async def _call_provider(provider: LLMProvider, system: str, user: str) -> dict | None:
    """Call one provider's chat-completions endpoint and return parsed JSON, or None."""
    async with httpx.AsyncClient(timeout=settings.LLM_TIMEOUT_SECONDS) as client:
        resp = await client.post(
            f"{provider.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {provider.api_key}"},
            json={
                "model": provider.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": 0.2,
            },
        )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        return _extract_json(content)


async def complete_json(system: str, user: str) -> dict | None:
    """Return a JSON object from the first provider that succeeds, else None.

    Never raises: any provider error (network, 429, 5xx, bad JSON) advances to the next
    provider, and exhausting the chain returns None so the caller can fall back.
    """
    if not settings.LLM_ENABLED:
        return None
    for provider in enabled_providers():
        try:
            result = await _call_provider(provider, system, user)
            if result is not None:
                return result
            logger.debug("LLM provider %s returned unparseable content", provider.name)
        except Exception as e:  # noqa: BLE001 - deliberately fall through to next provider
            logger.warning("LLM provider %s failed: %s", provider.name, e)
    return None
