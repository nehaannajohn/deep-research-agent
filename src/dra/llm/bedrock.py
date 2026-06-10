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
        kwargs = {
            "modelId": self.model_id,
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            "inferenceConfig": {"temperature": temperature, "maxTokens": max_tokens},
        }
        if system:
            kwargs["system"] = [{"text": system}]
        resp = self.client.converse(**kwargs)
        return resp["output"]["message"]["content"][0]["text"]

    def complete_json(self, prompt: str, **kw) -> dict:
        return json.loads(self.complete(prompt, **kw))
