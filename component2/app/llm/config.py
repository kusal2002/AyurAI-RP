"""LLM provider configuration, read only from environment variables.

The API key is never printed: it is excluded from repr() and from
describe(), and error messages name the variable, never its value.
"""

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


PROVIDERS = ("anthropic", "openai")
# Claude is the primary provider. OpenAI has no default model: it is a
# comparison baseline and its model must be chosen explicitly.
DEFAULT_MODELS = {"anthropic": "claude-opus-5-5"}
# Provider-specific key variables, used when C2_LLM_API_KEY is not set.
PROVIDER_KEY_VARIABLES = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
}
EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")


class LLMConfigurationError(ValueError):
    """The LLM provider is missing or misconfigured. Never contains a key."""


def _env(name: str) -> str | None:
    value = os.getenv(name)
    return value.strip() if value and value.strip() else None


def _env_number(name: str, default, kind=int, minimum=1):
    raw = _env(name)
    if raw is None:
        return default
    try:
        value = kind(raw)
    except ValueError as exc:
        raise LLMConfigurationError(f"{name} must be a number.") from exc
    if value < minimum:
        raise LLMConfigurationError(f"{name} must be >= {minimum}.")
    return value


@dataclass(frozen=True)
class LLMSettings:
    provider: str
    model: str
    api_key: str = field(repr=False)
    # Optional endpoint for a compatible third-party gateway.
    base_url: str | None = None
    max_tokens: int = 4096
    timeout_seconds: float = 120.0
    max_retries: int = 2
    # Claude only: output_config.effort. None keeps the model default.
    effort: str | None = None
    # Claude only: server-side refusal fallback ("default" routing). The
    # model that actually answered is recorded on every response.
    refusal_fallback: bool = True

    def describe(self) -> dict:
        """Settings safe to write into reports (no key)."""
        return {
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
            "max_tokens": self.max_tokens,
            "effort": self.effort,
            "refusal_fallback": self.refusal_fallback,
            "api_key_configured": bool(self.api_key),
        }


def load_llm_settings() -> LLMSettings:
    """Read C2_LLM_* variables. Raises LLMConfigurationError if unusable."""
    provider = (_env("C2_LLM_PROVIDER") or "anthropic").lower()
    if provider not in PROVIDERS:
        raise LLMConfigurationError(
            f"C2_LLM_PROVIDER must be one of {', '.join(PROVIDERS)}."
        )
    model = _env("C2_LLM_MODEL") or DEFAULT_MODELS.get(provider)
    if not model:
        raise LLMConfigurationError(
            f"C2_LLM_MODEL must be set for provider {provider}."
        )
    key_variable = PROVIDER_KEY_VARIABLES[provider]
    api_key = _env("C2_LLM_API_KEY") or _env(key_variable)
    if not api_key:
        raise LLMConfigurationError(
            f"No API key: set C2_LLM_API_KEY (or {key_variable}) in .env."
        )
    effort = _env("C2_LLM_EFFORT")
    if effort is not None and effort not in EFFORT_LEVELS:
        raise LLMConfigurationError(
            f"C2_LLM_EFFORT must be one of {', '.join(EFFORT_LEVELS)}."
        )
    fallback = (_env("C2_LLM_REFUSAL_FALLBACK") or "on").lower()
    if fallback not in ("on", "off"):
        raise LLMConfigurationError("C2_LLM_REFUSAL_FALLBACK must be on or off.")
    return LLMSettings(
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=_env("C2_LLM_BASE_URL"),
        max_tokens=_env_number("C2_LLM_MAX_TOKENS", 4096),
        timeout_seconds=_env_number("C2_LLM_TIMEOUT", 120.0, kind=float),
        max_retries=_env_number("C2_LLM_MAX_RETRIES", 2, minimum=0),
        effort=effort,
        refusal_fallback=fallback == "on",
    )
