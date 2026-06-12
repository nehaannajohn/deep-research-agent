"""OpenAI baseline **collection** client (spec §2, stretch baseline).

COLLECTION side for the OpenAI web-search baseline: calls the OpenAI
chat-completions API with the built-in web search (``web_search_options``) and
produces the raw response the SCORING-side ``OpenAIAdapter`` consumes. Same
injectable pattern as the Perplexity client (HTTP poster injected; fake in
tests, no network).

OpenAI is the *stretch* target — the caller is responsible for catching
availability errors and continuing; this client just builds the request and
parses the response.

Endpoint/format note: the available web-search model with this key is
``gpt-4o-search-preview``, which is a **chat-completions** model that takes
``web_search_options`` (NOT the Responses API ``/v1/responses`` tool form, which
404s for this model). Web citations come back as ``message.annotations`` of type
``url_citation`` with the URL nested under a ``url_citation`` object.

``query(prompt) -> dict`` returns::

    {"text": str, "citations": list[str], "urls": list[str], "raw": dict}

``text`` is the message content; ``citations``/``urls`` are the de-duplicated
``url_citation`` annotation URLs; ``raw`` is the full provider JSON.
"""
from __future__ import annotations

from typing import Callable

__all__ = ["OpenAIClient", "DEFAULT_SYSTEM_PROMPT"]

HttpPoster = Callable[..., object]

DEFAULT_ENDPOINT = "https://api.openai.com/v1/chat/completions"

DEFAULT_SYSTEM_PROMPT = (
    "You are a deep research assistant. Produce a structured, evidence-backed "
    "report. Separate claims from evidence. Indicate a confidence level for "
    "each major claim. Use web search extensively to ground your claims."
)


class OpenAIClient:
    """Minimal injectable client for the OpenAI chat-completions web-search API."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-search-preview",
        http: "HttpPoster | None" = None,
        endpoint: str = DEFAULT_ENDPOINT,
        system_prompt: str = DEFAULT_SYSTEM_PROMPT,
        timeout: int = 300,
    ):
        if not api_key:
            raise ValueError("OpenAIClient requires a non-empty api_key")
        self.api_key = api_key
        self.model = model
        self.endpoint = endpoint
        self.system_prompt = system_prompt
        self.timeout = timeout
        self._http = http

    # -- request build -----------------------------------------------------
    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _payload(self, prompt: str) -> dict:
        return {
            "model": self.model,
            "web_search_options": {},
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt},
            ],
        }

    # -- response parse ----------------------------------------------------
    @staticmethod
    def _ann_url(ann: dict) -> str:
        """A url_citation annotation nests the url under ``url_citation`` (chat
        completions); tolerate a flat ``url`` too."""
        if ann.get("type") != "url_citation":
            return ""
        nested = ann.get("url_citation") or {}
        return nested.get("url", "") or ann.get("url", "") or ""

    @classmethod
    def _parse(cls, data: dict) -> dict:
        choices = data.get("choices") or []
        text = ""
        annotations: list = []
        if choices:
            msg = choices[0].get("message") or {}
            text = msg.get("content", "") or ""
            annotations = msg.get("annotations", []) or []
        urls: list[str] = []
        seen: set[str] = set()
        for ann in annotations:
            url = cls._ann_url(ann)
            if url and url not in seen:
                seen.add(url)
                urls.append(url)
        return {
            "text": text,
            "citations": list(urls),
            "urls": list(urls),
            "raw": data,
        }

    # -- public ------------------------------------------------------------
    def query(self, prompt: str) -> dict:
        poster = self._http
        if poster is None:
            import requests

            poster = requests.post
        resp = poster(
            self.endpoint,
            headers=self._headers(),
            json=self._payload(prompt),
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return self._parse(resp.json())
