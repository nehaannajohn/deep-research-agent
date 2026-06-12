"""Thin Anthropic Messages API chat wrapper.

Mirrors the `BedrockChat.complete(prompt) -> str` interface so it can drop into
model-agnostic call sites (e.g. the Fable reference generator). Uses the user's
**personal Anthropic account** via the public Messages API — chosen over Bedrock's
Fable, which requires a data-sharing opt-in the user won't enable.

The HTTP poster is **injectable** so unit tests can stub it — no live calls in
tests. The default poster uses `requests` if available, else stdlib `urllib`.

The API key is never logged.
"""
from __future__ import annotations

import json
import time
from typing import Callable, Optional

__all__ = ["AnthropicChat", "AnthropicAPIError", "default_http_poster"]

API_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

# An injectable poster: (url, headers, json_body, timeout) -> (status_code, body_dict).
HttpPoster = Callable[[str, dict, dict, float], "tuple[int, dict]"]


class AnthropicAPIError(RuntimeError):
    """Raised when the Anthropic API returns a non-retryable / exhausted error.

    Never embeds the API key (only status + response body).
    """

    def __init__(self, status: int, body):
        self.status = status
        self.body = body
        super().__init__(f"Anthropic API error (status {status}): {str(body)[:500]}")


def default_http_poster(url: str, headers: dict, json_body: dict, timeout: float):
    """Default poster: prefer `requests`, fall back to stdlib `urllib`.

    Returns (status_code, parsed_json_body). Does not raise on HTTP error status
    so the caller can drive retry/backoff uniformly.
    """
    try:
        import requests  # type: ignore

        resp = requests.post(url, headers=headers, json=json_body, timeout=timeout)
        try:
            body = resp.json()
        except ValueError:
            body = {"_raw": resp.text}
        return resp.status_code, body
    except ImportError:
        pass

    import urllib.error
    import urllib.request

    data = json.dumps(json_body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw)
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            body = json.loads(raw)
        except ValueError:
            body = {"_raw": raw}
        return e.code, body


class AnthropicChat:
    """Anthropic Messages API client exposing `.complete(prompt) -> str`."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-fable-5",
        *,
        max_tokens: int = 4096,
        http: Optional[HttpPoster] = None,
        timeout: float = 120,
        max_retries: int = 4,
        base_backoff: float = 1.0,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if not api_key:
            raise ValueError("api_key is required")
        self._api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self._http = http or default_http_poster
        self.timeout = timeout
        self.max_retries = max_retries
        self.base_backoff = base_backoff
        self._sleep = sleep

    def _headers(self) -> dict:
        return {
            "x-api-key": self._api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "content-type": "application/json",
        }

    def complete(self, prompt: str) -> str:
        body = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }

        last_status = None
        last_body = None
        for attempt in range(self.max_retries + 1):
            status, resp = self._http(API_URL, self._headers(), body, self.timeout)
            if status == 200:
                return self._parse_text(resp)

            last_status, last_body = status, resp
            # Retry on 429 (rate limit) and 5xx (transient server errors).
            retryable = status == 429 or 500 <= status < 600
            if not retryable or attempt == self.max_retries:
                break
            self._sleep(self.base_backoff * (2 ** attempt))

        raise AnthropicAPIError(last_status, last_body)

    @staticmethod
    def _parse_text(resp: dict) -> str:
        """Join all `text`-type content blocks, skipping non-text ones.

        Models with extended thinking return ``content = [{type:thinking,...},
        {type:text,...}]`` (Fable does this on complex prompts), so taking
        ``content[0]`` grabs the thinking block. We concatenate every text block
        and ignore thinking/redacted ones. An empty result raises, so a
        thinking-only / max-tokens-during-thinking response is surfaced rather
        than silently returned as "".
        """
        try:
            blocks = resp.get("content", []) or []
            text = "".join(
                b.get("text", "") for b in blocks
                if isinstance(b, dict) and b.get("type") == "text"
            )
        except (AttributeError, TypeError) as e:
            raise AnthropicAPIError(200, resp) from e
        if not text:
            raise AnthropicAPIError(200, resp)
        return text
