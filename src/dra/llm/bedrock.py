"""Thin AWS Bedrock chat wrapper (Converse API).

The boto3 client is injectable so unit tests can stub it — no live calls in tests.
"""
from __future__ import annotations

import json
import re
from typing import Optional


def _balanced_spans(t: str, open_ch: str, close_ch: str):
    """Yield (start, substring) for every balanced `open_ch..close_ch` span in `t`,
    honoring string literals (so braces inside quotes don't affect depth)."""
    i, n = 0, len(t)
    while i < n:
        if t[i] == open_ch:
            depth = 0
            in_str = esc = False
            for j in range(i, n):
                ch = t[j]
                if in_str:
                    if esc:
                        esc = False
                    elif ch == "\\":
                        esc = True
                    elif ch == '"':
                        in_str = False
                elif ch == '"':
                    in_str = True
                elif ch == open_ch:
                    depth += 1
                elif ch == close_ch:
                    depth -= 1
                    if depth == 0:
                        yield i, t[i:j + 1]
                        break
        i += 1


def _extract_json(text: str):
    """Parse JSON from a model response that may wrap it in ```fences```, prose, or emit
    several JSON values (some models ramble and produce more than one). Returns the FIRST
    balanced, parseable JSON value (outermost-first) — never a greedy first-brace-to-last-
    brace span, which would swallow multiple objects + the prose between them."""
    t = (text or "").strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass
    fence = re.search(r"```(?:json)?\s*(.*?)```", t, re.DOTALL)
    if fence:
        try:
            return json.loads(fence.group(1).strip())
        except json.JSONDecodeError:
            pass
    candidates = [c for ch in (("{", "}"), ("[", "]")) for c in _balanced_spans(t, *ch)]
    for _start, span in sorted(candidates, key=lambda c: c[0]):  # earliest (outermost) first
        try:
            return json.loads(span)
        except json.JSONDecodeError:
            continue
    raise ValueError(f"No JSON found in model output: {t[:200]!r}")


def _boto_config(read_timeout: int, connect_timeout: int = 10):
    """Build a botocore Config with bounded timeouts so stuck/expired-creds calls fail fast."""
    from botocore.config import Config

    return Config(read_timeout=read_timeout, connect_timeout=connect_timeout,
                  retries={"max_attempts": 2, "mode": "standard"})


class BedrockChat:
    def __init__(self, model_id: str, client=None, region: str = "us-east-1", timeout: int = 60):
        self.model_id = model_id
        self.timeout = timeout
        if client is None:  # pragma: no cover - exercised only with real AWS creds
            import boto3

            client = boto3.client("bedrock-runtime", region_name=region, config=_boto_config(timeout))
        self.client = client

    def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 8192,
    ) -> str:
        messages = [{"role": "user", "content": [{"text": prompt}]}]

        def _request(include_temperature: bool):
            cfg = {"maxTokens": max_tokens}
            if include_temperature:
                cfg["temperature"] = temperature
            kwargs = {"modelId": self.model_id, "messages": messages, "inferenceConfig": cfg}
            if system:
                kwargs["system"] = [{"text": system}]
            return self.client.converse(**kwargs)

        try:
            resp = _request(include_temperature=True)
        except Exception as e:
            # Extended-thinking models (e.g. Claude Opus 4.x) reject `temperature`.
            if "temperature" in str(e).lower():
                resp = _request(include_temperature=False)
            else:
                raise

        # Reasoning models (GPT-OSS, R1, extended-thinking Claude) emit a
        # reasoningContent block before the answer — return the first text block.
        for block in resp["output"]["message"]["content"]:
            if "text" in block:
                return block["text"]
        return ""

    def complete_json(self, prompt: str, **kw):
        return _extract_json(self.complete(prompt, **kw))
