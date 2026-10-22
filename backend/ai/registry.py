"""Resolve the active AI provider from settings.

``AI_PROVIDER=auto`` picks Anthropic when its API key is configured, Gemini when only a Gemini
key is configured, and the explicitly marked Demo provider otherwise. The frontend reads
``demo_mode`` from ``/api/v1/meta/`` and shows a permanent banner, so a stub is never mistaken for
a real integration.
"""

from __future__ import annotations

from functools import lru_cache

from django.conf import settings

from .base import AIProvider

_override: AIProvider | None = None


@lru_cache(maxsize=1)
def _resolve() -> AIProvider:
    choice = settings.AI_PROVIDER
    if choice == "auto":
        if settings.ANTHROPIC_API_KEY:
            choice = "anthropic"
        elif settings.GEMINI_API_KEY:
            choice = "gemini"
        else:
            choice = "demo"
    if choice == "anthropic":
        if not settings.ANTHROPIC_API_KEY:
            raise RuntimeError("AI_PROVIDER=anthropic requires ANTHROPIC_API_KEY")
        from .anthropic_provider import AnthropicProvider

        return AnthropicProvider()
    if choice == "gemini":
        if not settings.GEMINI_API_KEY:
            raise RuntimeError("AI_PROVIDER=gemini requires GEMINI_API_KEY")
        from .gemini_provider import GeminiProvider

        return GeminiProvider()
    if choice == "demo":
        from .demo import DemoProvider

        return DemoProvider()
    raise RuntimeError(f"Unknown AI_PROVIDER: {choice}")


def get_provider() -> AIProvider:
    return _override if _override is not None else _resolve()


def provider_status() -> dict:
    provider = get_provider()
    return {"name": provider.name, "demo_mode": provider.demo_mode}


def set_provider_override(provider: AIProvider | None) -> None:
    """Test hook: inject a scripted provider for the whole process. Never used in production code paths."""
    global _override
    _override = provider


def reset_provider_cache() -> None:
    _resolve.cache_clear()
