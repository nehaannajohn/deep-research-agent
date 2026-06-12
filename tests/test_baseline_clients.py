"""Unit tests for the baseline COLLECTION clients (fakes only, no network).

Covers request-payload shape and response parsing for both the Perplexity and
OpenAI clients. The HTTP poster is injected as a fake that records the call and
returns a canned provider-shaped response.
"""
from __future__ import annotations

import pytest

from dra.eval.pipeline.baselines.openai_client import OpenAIClient
from dra.eval.pipeline.baselines.perplexity_client import PerplexityClient


class _FakeResponse:
    def __init__(self, payload: dict):
        self._payload = payload
        self.raised = False

    def raise_for_status(self) -> None:
        self.raised = True

    def json(self) -> dict:
        return self._payload


class _FakePoster:
    """Records the last call and returns a fixed response."""

    def __init__(self, response_payload: dict):
        self._response = _FakeResponse(response_payload)
        self.calls: list[dict] = []

    def __call__(self, url, headers=None, json=None, timeout=None):
        self.calls.append(
            {"url": url, "headers": headers, "json": json, "timeout": timeout}
        )
        return self._response


# --------------------------------------------------------------------------
# Perplexity
# --------------------------------------------------------------------------

def test_perplexity_request_payload_shape():
    poster = _FakePoster({"choices": [], "citations": []})
    client = PerplexityClient(api_key="pk-test", model="sonar-pro", http=poster)
    client.query("What is RLHF?")

    assert len(poster.calls) == 1
    call = poster.calls[0]
    assert call["url"] == "https://api.perplexity.ai/chat/completions"
    assert call["headers"]["Authorization"] == "Bearer pk-test"
    body = call["json"]
    assert body["model"] == "sonar-pro"
    assert body["return_citations"] is True
    # system + user messages, user carries the prompt
    roles = [m["role"] for m in body["messages"]]
    assert roles == ["system", "user"]
    assert body["messages"][1]["content"] == "What is RLHF?"


def test_perplexity_response_parse():
    payload = {
        "choices": [{"message": {"content": "RLHF aligns models with human feedback."}}],
        "citations": ["https://example.com/a", "https://example.com/b"],
        "usage": {"total_tokens": 42},
    }
    poster = _FakePoster(payload)
    client = PerplexityClient(api_key="pk-test", http=poster)
    out = client.query("q")

    assert out["text"] == "RLHF aligns models with human feedback."
    assert out["citations"] == ["https://example.com/a", "https://example.com/b"]
    assert out["urls"] == out["citations"]
    assert out["raw"] is payload
    assert poster._response.raised is True


def test_perplexity_empty_choices_safe():
    poster = _FakePoster({"choices": [], "citations": []})
    client = PerplexityClient(api_key="pk-test", http=poster)
    out = client.query("q")
    assert out["text"] == ""
    assert out["citations"] == []


def test_perplexity_requires_api_key():
    with pytest.raises(ValueError):
        PerplexityClient(api_key="")


# --------------------------------------------------------------------------
# OpenAI
# --------------------------------------------------------------------------

def test_openai_request_payload_shape():
    poster = _FakePoster({"choices": []})
    client = OpenAIClient(api_key="sk-test", model="gpt-4o-search-preview", http=poster)
    client.query("Explain backpropagation.")

    assert len(poster.calls) == 1
    call = poster.calls[0]
    assert call["url"] == "https://api.openai.com/v1/chat/completions"
    assert call["headers"]["Authorization"] == "Bearer sk-test"
    body = call["json"]
    assert body["model"] == "gpt-4o-search-preview"
    assert body["web_search_options"] == {}
    roles = [m["role"] for m in body["messages"]]
    assert roles == ["system", "user"]
    assert body["messages"][1]["content"] == "Explain backpropagation."


def test_openai_response_parse_text_and_dedup_citations():
    payload = {
        "choices": [
            {
                "message": {
                    "content": "Backprop computes gradients.",
                    "annotations": [
                        {"type": "url_citation", "url_citation": {"url": "https://x.com/1", "title": "A"}},
                        {"type": "url_citation", "url_citation": {"url": "https://x.com/1", "title": "A-dup"}},
                        {"type": "url_citation", "url_citation": {"url": "https://x.com/2", "title": "B"}},
                    ],
                }
            }
        ]
    }
    poster = _FakePoster(payload)
    client = OpenAIClient(api_key="sk-test", http=poster)
    out = client.query("q")

    assert out["text"] == "Backprop computes gradients."
    assert out["urls"] == ["https://x.com/1", "https://x.com/2"]  # deduped, ordered
    assert out["citations"] == out["urls"]
    assert out["raw"] is payload


def test_openai_empty_output_safe():
    poster = _FakePoster({"choices": []})
    client = OpenAIClient(api_key="sk-test", http=poster)
    out = client.query("q")
    assert out["text"] == ""
    assert out["citations"] == []


def test_openai_requires_api_key():
    with pytest.raises(ValueError):
        OpenAIClient(api_key="")
