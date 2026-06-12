"""Perplexity Sonar baseline **collection** client (spec §2, the black-box path).

This is the COLLECTION side: it calls the Perplexity API and produces the raw
response that the SCORING-side ``PerplexityAdapter`` later consumes. We keep it
tiny and testable: the HTTP poster is injected, so the request-build and
response-parse can be unit-tested with a fake (no network).

``query(prompt) -> dict`` returns::

    {"text": str, "citations": list[str], "urls": list[str], "raw": dict}

``text`` is the model narrative; ``citations``/``urls`` are the returned cited
sources (Perplexity returns a flat ``citations`` list of URLs); ``raw`` is the
full provider JSON for archival / downstream normalization.
"""
from __future__ import annotations

from typing import Callable

__all__ = ["PerplexityClient", "DEFAULT_SYSTEM_PROMPT"]

# Poster signature: (url, headers, json_payload, timeout) -> response-like with
# ``.json()`` and ``.raise_for_status()`` (the ``requests.post`` contract).
HttpPoster = Callable[..., object]

DEFAULT_ENDPOINT = "https://api.perplexity.ai/chat/completions"

DEFAULT_SYSTEM_PROMPT = (
    "You are a deep research assistant. Produce a structured, evidence-backed "
    "report. Separate claims from evidence. Indicate a confidence level for "
    "each major claim."
)


class PerplexityClient:
    """Minimal injectable client for the Perplexity Sonar chat-completions API."""

    def __init__(
        self,
        api_key: str,
        model: str = "sonar-pro",
        http: "HttpPoster | None" = None,
        endpoint: str = DEFAULT_ENDPOINT,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        timeout: int = 120,
    ):
        if not api_key:
            raise ValueError("PerplexityClient requires a non-empty api_key")
        self.api_key = api_key
        self.model = model
        self.endpoint = endpoint
        self.system_prompt = system_prompt
        self.timeout = timeout
        self._http = http  # injected for tests; lazily import requests otherwise

    # -- request build -----------------------------------------------------
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _payload(self, prompt: str) -> dict:
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
            "return_citations": True,
            "return_related_questions": False,
        }

    # -- response parse ----------------------------------------------------
    @staticmethod
    def _parse(data: dict) -> dict:
        choices = data.get("choices") or []
        text = ""
        if choices:
            text = (choices[0].get("message") or {}).get("content", "") or ""
        citations = list(data.get("citations") or [])
        # Perplexity citations are URLs; expose both keys the adapters may use.
        return {
            "text": text,
            "citations": citations,
            "urls": list(citations),
            "raw": data,
        }

    # -- public ------------------------------------------------------------
    def query(self, prompt: str) -> dict:
        poster = self._http
        if poster is None:
            import requests  # local import: keep module importable without network deps

            poster = requests.post
        resp = poster(
            self.endpoint,
            headers=self._headers(),
            json=self._payload(prompt),
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return self._parse(resp.json())
