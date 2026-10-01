"""
LLM provider adapter.

The app doesn't set up its own LLM agent — it calls out to a Claude or OpenAI
model using an API key supplied via environment variables. Both providers
implement the same tiny interface (`generate(system_prompt, user_prompt) -> str`)
so the rest of the app doesn't care which one is active.

Provider choice: env var LLM_PROVIDER ("claude" | "openai"), overridable per
request from the web form.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod


class LLMConfigError(RuntimeError):
    """Raised when a provider is selected but its API key/config is missing."""


class LLMProvider(ABC):
    name: str

    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Return the raw text response from the model (expected to be JSON)."""


class ClaudeProvider(LLMProvider):
    name = "claude"

    def __init__(self) -> None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise LLMConfigError("ANTHROPIC_API_KEY is not set in the environment (.env).")
        import anthropic  # imported lazily so the app can run without the package if unused

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=8000,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        return "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        )


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise LLMConfigError("OPENAI_API_KEY is not set in the environment (.env).")
        from openai import OpenAI  # imported lazily, same reasoning as above

        self._client = OpenAI(api_key=api_key)
        self._model = os.getenv("OPENAI_MODEL", "gpt-4o")

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content or ""


_PROVIDERS = {
    "claude": ClaudeProvider,
    "openai": OpenAIProvider,
}


def get_provider(name: str | None = None) -> LLMProvider:
    """Instantiate the requested provider (or the env default if none given)."""
    key = (name or os.getenv("LLM_PROVIDER", "claude")).lower()
    if key not in _PROVIDERS:
        raise LLMConfigError(f"Unknown LLM provider: {key}. Available: {list(_PROVIDERS)}")
    return _PROVIDERS[key]()


def available_providers() -> list[str]:
    return list(_PROVIDERS)
