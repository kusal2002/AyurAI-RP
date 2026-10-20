"""Provider-neutral text completion: Claude (Anthropic SDK) or OpenAI.

Both providers expose one call, complete(system, prompt) -> LLMResponse.
Claude goes through the official `anthropic` SDK. OpenAI is an optional
comparison provider called over plain HTTP (Chat Completions), so it
needs no extra dependency. An `http_client` can be injected for tests.

Errors are re-raised as LLMRequestError carrying the provider's status
code and error type only, so no request content or key is echoed.
"""

from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx2

from app.llm.config import LLMConfigurationError, LLMSettings, load_llm_settings


DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
ANTHROPIC_FALLBACK_BETA = "server-side-fallback-2026-07-01"


class LLMRequestError(RuntimeError):
    """The provider call failed. The message never contains the key."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class LLMRefusalError(LLMRequestError):
    """The model declined the request (Claude stop_reason "refusal")."""


@dataclass
class LLMResponse:
    text: str
    provider: str
    # Model requested and model that actually answered (they differ when a
    # Claude refusal fallback served the turn).
    requested_model: str
    served_model: str
    stop_reason: str | None
    usage: dict[str, int] = field(default_factory=dict)
    fallback_used: bool = False


class LLMClient(Protocol):
    settings: LLMSettings

    def complete(self, system: str, prompt: str) -> LLMResponse: ...


class AnthropicClient:
    def __init__(self, settings: LLMSettings, http_client: Any = None):
        import anthropic

        self.settings = settings
        self._anthropic = anthropic
        options: dict[str, Any] = {
            "api_key": settings.api_key,
            "timeout": settings.timeout_seconds,
            "max_retries": settings.max_retries,
        }
        if settings.base_url:
            options["base_url"] = settings.base_url
        if http_client is not None:
            options["http_client"] = http_client
        self._client = anthropic.Anthropic(**options)

    def complete(self, system: str, prompt: str) -> LLMResponse:
        anthropic = self._anthropic
        params: dict[str, Any] = {
            "model": self.settings.model,
            "max_tokens": self.settings.max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        }
        if self.settings.effort:
            params["output_config"] = {"effort": self.settings.effort}
        try:
            if self.settings.refusal_fallback:
                response = self._client.beta.messages.create(
                    betas=[ANTHROPIC_FALLBACK_BETA], fallbacks="default", **params
                )
            else:
                response = self._client.messages.create(**params)
        except anthropic.APIStatusError as exc:
            raise LLMRequestError(
                f"Anthropic API error {exc.status_code} "
                f"({type(exc).__name__}).",
                exc.status_code,
            ) from None
        except anthropic.APIConnectionError as exc:
            raise LLMRequestError(
                f"Anthropic API connection failed ({type(exc).__name__})."
            ) from None

        if response.stop_reason == "refusal":
            details = getattr(response, "stop_details", None)
            category = getattr(details, "category", None)
            raise LLMRefusalError(
                f"Claude declined the request (category: {category})."
            )
        text = "".join(
            block.text for block in response.content if block.type == "text"
        )
        iterations = getattr(response.usage, "iterations", None) or []
        return LLMResponse(
            text=text,
            provider="anthropic",
            requested_model=self.settings.model,
            served_model=response.model,
            stop_reason=response.stop_reason,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            fallback_used=any(
                getattr(entry, "type", None) == "fallback_message"
                for entry in iterations
            ),
        )


class OpenAIClient:
    """Chat Completions over HTTP (OpenAI or a compatible gateway)."""

    def __init__(self, settings: LLMSettings, http_client: httpx2.Client | None = None):
        self.settings = settings
        self._base_url = (settings.base_url or DEFAULT_OPENAI_BASE_URL).rstrip("/")
        self._client = http_client or httpx2.Client(timeout=settings.timeout_seconds)

    def complete(self, system: str, prompt: str) -> LLMResponse:
        body = {
            "model": self.settings.model,
            "max_completion_tokens": self.settings.max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        }
        headers = {"Authorization": f"Bearer {self.settings.api_key}"}
        response = None
        for attempt in range(self.settings.max_retries + 1):
            try:
                response = self._client.post(
                    f"{self._base_url}/chat/completions", json=body, headers=headers
                )
            except httpx2.HTTPError as exc:
                if attempt == self.settings.max_retries:
                    raise LLMRequestError(
                        f"OpenAI API connection failed ({type(exc).__name__})."
                    ) from None
                continue
            if response.status_code in (408, 409, 429) or response.status_code >= 500:
                if attempt < self.settings.max_retries:
                    continue
            break
        if response.status_code != 200:
            raise LLMRequestError(
                f"OpenAI API error {response.status_code}.", response.status_code
            )
        try:
            data = response.json()
            choice = data["choices"][0]
            text = choice["message"].get("content") or ""
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMRequestError("OpenAI API returned an unexpected body.") from exc
        if choice["message"].get("refusal"):
            raise LLMRefusalError("The OpenAI model declined the request.")
        usage = data.get("usage") or {}
        return LLMResponse(
            text=text,
            provider="openai",
            requested_model=self.settings.model,
            served_model=data.get("model") or self.settings.model,
            stop_reason=choice.get("finish_reason"),
            usage={
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
            },
        )


def create_llm_client(
    settings: LLMSettings | None = None, http_client: Any = None
) -> LLMClient:
    """Build the configured client. Raises LLMConfigurationError."""
    settings = settings or load_llm_settings()
    if settings.provider == "anthropic":
        return AnthropicClient(settings, http_client)
    if settings.provider == "openai":
        return OpenAIClient(settings, http_client)
    raise LLMConfigurationError(f"Unsupported provider {settings.provider}.")
