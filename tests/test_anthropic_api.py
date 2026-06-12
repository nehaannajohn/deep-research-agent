"""Unit tests for AnthropicChat — fake http poster, NO network."""
from __future__ import annotations

import pytest

from dra.llm.anthropic_api import AnthropicAPIError, AnthropicChat, API_URL


class FakeHttp:
    """Records calls; returns scripted (status, body) responses in order."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def __call__(self, url, headers, json_body, timeout):
        self.calls.append({"url": url, "headers": headers, "body": json_body, "timeout": timeout})
        return self._responses.pop(0)


def _ok(text="hello"):
    return 200, {"content": [{"type": "text", "text": text}]}


def test_request_payload_and_headers_shape():
    http = FakeHttp([_ok("hi there")])
    chat = AnthropicChat("sk-test-key", model="claude-fable-5", max_tokens=2048, http=http)
    out = chat.complete("What is 2+2?")

    assert out == "hi there"
    assert len(http.calls) == 1
    call = http.calls[0]
    assert call["url"] == API_URL
    # Headers shape
    assert call["headers"]["x-api-key"] == "sk-test-key"
    assert call["headers"]["anthropic-version"] == "2023-06-01"
    assert call["headers"]["content-type"] == "application/json"
    # Body shape
    body = call["body"]
    assert body["model"] == "claude-fable-5"
    assert body["max_tokens"] == 2048
    assert body["messages"] == [{"role": "user", "content": "What is 2+2?"}]


def test_response_text_parse():
    http = FakeHttp([(200, {"content": [{"type": "text", "text": "the answer"}]})])
    chat = AnthropicChat("k", http=http)
    assert chat.complete("q") == "the answer"


def test_429_then_success_retry():
    http = FakeHttp([
        (429, {"error": {"type": "rate_limit_error"}}),
        _ok("recovered"),
    ])
    sleeps = []
    chat = AnthropicChat("k", http=http, sleep=lambda s: sleeps.append(s))
    out = chat.complete("q")

    assert out == "recovered"
    assert len(http.calls) == 2  # retried once
    assert len(sleeps) == 1  # backed off once
    assert sleeps[0] > 0


def test_5xx_retries_then_raises_without_leaking_key():
    http = FakeHttp([
        (503, {"error": "unavailable"}),
        (502, {"error": "bad gateway"}),
    ])
    chat = AnthropicChat("super-secret-key", http=http, max_retries=1, sleep=lambda s: None)
    with pytest.raises(AnthropicAPIError) as exc:
        chat.complete("q")
    assert exc.value.status == 502
    assert "super-secret-key" not in str(exc.value)


def test_non_retryable_4xx_raises_immediately():
    http = FakeHttp([(400, {"error": {"type": "invalid_request_error"}})])
    chat = AnthropicChat("k", http=http, sleep=lambda s: None)
    with pytest.raises(AnthropicAPIError) as exc:
        chat.complete("q")
    assert exc.value.status == 400
    assert len(http.calls) == 1  # no retry on 400


def test_empty_api_key_rejected():
    with pytest.raises(ValueError):
        AnthropicChat("")
