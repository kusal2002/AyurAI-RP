"""LLM adapter: configuration, Claude and OpenAI clients over mocked HTTP."""

import json
import socket

import anthropic
import httpx2
import pytest

from app.llm.client import (
    ANTHROPIC_FALLBACK_BETA,
    AnthropicClient,
    LLMRefusalError,
    LLMRequestError,
    OpenAIClient,
    create_llm_client,
)
from app.llm.config import LLMConfigurationError, LLMSettings, load_llm_settings
from app.llm.grounding import (
    PROVISIONAL_LABEL,
    extract_ids,
    has_provisional_label,
    parse_json_object,
    unsafe_phrases,
    with_provisional_label,
)

SECRET = "sk-test-not-a-real-key-0123456789"
LLM_VARIABLES = (
    "C2_LLM_PROVIDER", "C2_LLM_MODEL", "C2_LLM_API_KEY", "C2_LLM_BASE_URL",
    "C2_LLM_MAX_TOKENS", "C2_LLM_TIMEOUT", "C2_LLM_MAX_RETRIES", "C2_LLM_EFFORT",
    "C2_LLM_REFUSAL_FALLBACK", "ANTHROPIC_API_KEY", "OPENAI_API_KEY",
)


@pytest.fixture(autouse=True)
def no_network_and_clean_env(monkeypatch):
    def refuse(*_args, **_kwargs):
        raise AssertionError("network access attempted in an LLM test")

    monkeypatch.setattr(socket.socket, "connect", refuse)
    for name in LLM_VARIABLES:
        monkeypatch.delenv(name, raising=False)


def _anthropic_client(handler, **overrides) -> AnthropicClient:
    settings = LLMSettings(
        provider="anthropic", model="claude-opus-5-5", api_key=SECRET, max_retries=0, **overrides
    )
    http = anthropic.DefaultHttpxClient(transport=httpx2.MockTransport(handler))
    return AnthropicClient(settings, http_client=http)


def _message(text="hello", stop_reason="end_turn", model="claude-opus-5-5", **extra):
    body = {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": [{"type": "text", "text": text}],
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {"input_tokens": 12, "output_tokens": 3},
    }
    body.update(extra)
    return body


# --- configuration ----------------------------------------------------------

def test_defaults_to_claude_and_hides_the_key(monkeypatch):
    monkeypatch.setenv("C2_LLM_API_KEY", SECRET)
    settings = load_llm_settings()
    assert settings.provider == "anthropic"
    assert settings.model == "claude-opus-5-5"
    assert settings.refusal_fallback is True
    assert SECRET not in repr(settings)
    assert SECRET not in json.dumps(settings.describe())
    assert settings.describe()["api_key_configured"] is True


def test_provider_specific_key_variable_is_accepted(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", SECRET)
    assert load_llm_settings().api_key == SECRET


def test_missing_key_names_the_variable_only(monkeypatch):
    with pytest.raises(LLMConfigurationError, match="C2_LLM_API_KEY"):
        load_llm_settings()


def test_openai_requires_an_explicit_model(monkeypatch):
    monkeypatch.setenv("C2_LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", SECRET)
    with pytest.raises(LLMConfigurationError, match="C2_LLM_MODEL"):
        load_llm_settings()
    monkeypatch.setenv("C2_LLM_MODEL", "gpt-test")
    assert isinstance(create_llm_client(), OpenAIClient)


@pytest.mark.parametrize("name, value", [
    ("C2_LLM_PROVIDER", "gemini"),
    ("C2_LLM_EFFORT", "extreme"),
    ("C2_LLM_REFUSAL_FALLBACK", "maybe"),
    ("C2_LLM_MAX_TOKENS", "0"),
    ("C2_LLM_TIMEOUT", "soon"),
])
def test_invalid_settings_are_rejected(monkeypatch, name, value):
    monkeypatch.setenv("C2_LLM_API_KEY", SECRET)
    monkeypatch.setenv(name, value)
    with pytest.raises(LLMConfigurationError) as excinfo:
        load_llm_settings()
    assert SECRET not in str(excinfo.value)


# --- Claude -----------------------------------------------------------------

def test_claude_request_shape_and_response():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["headers"] = request.headers
        seen["body"] = json.loads(request.content)
        return httpx2.Response(200, json=_message('{"decision": "abstain"}'))

    response = _anthropic_client(handler, effort="high").complete("system text", "user text")
    assert seen["url"].endswith("/v1/messages?beta=true") or seen["url"].endswith("/v1/messages")
    assert seen["headers"]["x-api-key"] == SECRET
    assert ANTHROPIC_FALLBACK_BETA in seen["headers"]["anthropic-beta"]
    body = seen["body"]
    assert body["model"] == "claude-opus-5-5"
    assert body["fallbacks"] == "default"
    assert body["system"] == "system text"
    assert body["messages"] == [{"role": "user", "content": "user text"}]
    assert body["output_config"] == {"effort": "high"}
    # Removed sampling and thinking-budget parameters are never sent.
    assert not {"temperature", "top_p", "top_k", "thinking"} & body.keys()
    assert response.text == '{"decision": "abstain"}'
    assert response.provider == "anthropic"
    assert response.served_model == "claude-opus-5-5"
    assert response.usage == {"input_tokens": 12, "output_tokens": 3}
    assert response.fallback_used is False


def test_claude_without_fallback_uses_plain_messages_endpoint():
    seen = {}

    def handler(request):
        seen["headers"] = request.headers
        seen["body"] = json.loads(request.content)
        return httpx2.Response(200, json=_message())

    _anthropic_client(handler, refusal_fallback=False).complete("s", "p")
    assert "anthropic-beta" not in seen["headers"]
    assert "fallbacks" not in seen["body"]
    assert "output_config" not in seen["body"]


def test_claude_records_the_model_that_served_a_fallback():
    def handler(request):
        return httpx2.Response(200, json=_message(
            model="claude-opus-4-8",
            usage={"input_tokens": 1, "output_tokens": 1,
                   "iterations": [{"type": "fallback_message", "input_tokens": 1, "output_tokens": 1}]},
        ))

    response = _anthropic_client(handler).complete("s", "p")
    assert response.requested_model == "claude-opus-5-5"
    assert response.served_model == "claude-opus-4-8"
    assert response.fallback_used is True


def test_claude_refusal_raises():
    def handler(request):
        return httpx2.Response(200, json=_message(
            text="", stop_reason="refusal",
            stop_details={"type": "refusal", "category": "bio", "explanation": None},
        ))

    with pytest.raises(LLMRefusalError, match="bio"):
        _anthropic_client(handler).complete("s", "p")


@pytest.mark.parametrize("status", [401, 429, 500])
def test_claude_http_errors_never_echo_the_key(status):
    def handler(request):
        return httpx2.Response(status, json={
            "type": "error", "error": {"type": "api_error", "message": f"bad key {SECRET}"},
        })

    with pytest.raises(LLMRequestError) as excinfo:
        _anthropic_client(handler).complete("s", "p")
    assert excinfo.value.status_code == status
    assert SECRET not in str(excinfo.value)


def test_claude_connection_error_is_wrapped():
    def handler(request):
        raise httpx2.ConnectError("unreachable", request=request)

    with pytest.raises(LLMRequestError, match="connection failed"):
        _anthropic_client(handler).complete("s", "p")


def test_claude_custom_base_url_for_a_gateway():
    seen = {}

    def handler(request):
        seen["host"] = request.url.host
        return httpx2.Response(200, json=_message())

    _anthropic_client(handler, base_url="https://gateway.example.test").complete("s", "p")
    assert seen["host"] == "gateway.example.test"


# --- OpenAI -----------------------------------------------------------------

def _openai_client(handler, max_retries=0, base_url=None) -> OpenAIClient:
    settings = LLMSettings(provider="openai", model="gpt-test", api_key=SECRET,
                           max_retries=max_retries, base_url=base_url)
    return OpenAIClient(settings, http_client=httpx2.Client(transport=httpx2.MockTransport(handler)))


def _completion(text="ok"):
    return {
        "model": "gpt-test-2026",
        "choices": [{"message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 7, "completion_tokens": 2},
    }


def test_openai_request_shape_and_response():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx2.Response(200, json=_completion("answer"))

    response = _openai_client(handler).complete("sys", "prompt")
    assert seen["url"] == "https://api.openai.com/v1/chat/completions"
    assert seen["auth"] == f"Bearer {SECRET}"
    assert seen["body"]["messages"] == [
        {"role": "system", "content": "sys"}, {"role": "user", "content": "prompt"},
    ]
    assert response.text == "answer"
    assert response.served_model == "gpt-test-2026"
    assert response.usage == {"input_tokens": 7, "output_tokens": 2}


def test_openai_retries_rate_limits_then_succeeds():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx2.Response(429) if len(calls) == 1 else httpx2.Response(200, json=_completion())

    assert _openai_client(handler, max_retries=1).complete("s", "p").text == "ok"
    assert len(calls) == 2


def test_openai_errors_and_refusals():
    with pytest.raises(LLMRequestError) as excinfo:
        _openai_client(lambda r: httpx2.Response(401, text=SECRET)).complete("s", "p")
    assert excinfo.value.status_code == 401 and SECRET not in str(excinfo.value)

    with pytest.raises(LLMRequestError, match="unexpected body"):
        _openai_client(lambda r: httpx2.Response(200, json={"choices": []})).complete("s", "p")

    refusal = {"choices": [{"message": {"content": None, "refusal": "no"}, "finish_reason": "stop"}]}
    with pytest.raises(LLMRefusalError):
        _openai_client(lambda r: httpx2.Response(200, json=refusal)).complete("s", "p")


def test_openai_gateway_base_url():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        return httpx2.Response(200, json=_completion())

    _openai_client(handler, base_url="https://gw.example.test/v1/").complete("s", "p")
    assert seen["url"] == "https://gw.example.test/v1/chat/completions"


# --- grounding helpers ------------------------------------------------------

def test_grounding_helpers():
    assert extract_ids("claim [CL-SBX-PALLOR] and PCL-0a1b2c, R-PANDU") == {
        "CL-SBX-PALLOR", "PCL-0a1b2c", "R-PANDU",
    }
    labelled = with_provisional_label("Pitta is involved.")
    assert labelled == f"{PROVISIONAL_LABEL}: Pitta is involved."
    assert with_provisional_label("unverified - practitioner review pending: Pitta is involved.") == labelled
    assert with_provisional_label(labelled) == labelled
    assert has_provisional_label("x Unverified – practitioner review pending y")
    assert parse_json_object('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json_object('Sure: {"a": [1]} done') == {"a": [1]}
    assert parse_json_object("no json") is None
    assert unsafe_phrases("Take 500 mg twice; this will cure you") == ["dosage", "efficacy_promise"]
    assert unsafe_phrases("This is a graph association, not a diagnosis.") == []
