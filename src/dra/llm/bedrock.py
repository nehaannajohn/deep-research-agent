"""Thin AWS Bedrock chat wrapper (Converse API).

The boto3 client is injectable so unit tests can stub it — no live calls in tests.
"""
from __future__ import annotations

import json
from typing import Optional


class BedrockChat:
    def __init__(self, model_id: str, client=None, region: str = "us-east-1"):
        self.model_id = model_id
        if client is None:  # pragma: no cover - exercised only with real AWS creds
            import boto3

            client = boto3.client("bedrock-runtime", region_name=region)
        self.client = client

    def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 1024,
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

    def complete_json(self, prompt: str, **kw) -> dict:
        return json.loads(self.complete(prompt, **kw))
