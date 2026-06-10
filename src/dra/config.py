"""Environment + per-role model assignment.

Model independence is a design requirement: the generator, the in-loop judge
verifier, and the evaluation panel must be different model *families* so biases
don't correlate. `assert_independence()` enforces the generator/in-loop split.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


def family(model_id: str) -> str:
    """Bedrock ids look like 'anthropic.claude-...', 'meta.llama3-...'. Family = prefix."""
    return model_id.split(".", 1)[0] if model_id else ""


@dataclass
class Config:
    region: str
    roles: dict
    panel_models: list
    exa_key: str = ""
    tavily_key: str = ""
    semantic_scholar_key: str = ""
    perplexity_key: str = ""
    wandb_key: str = ""

    def assert_independence(self) -> None:
        g = family(self.roles.get("generator", ""))
        j = family(self.roles.get("inloop_judge", ""))
        if g and j and g == j:
            raise ValueError(
                f"generator and in-loop judge must be different model families (both '{g}')"
            )


def load_config(env: "dict | None" = None) -> Config:
    if env is None:
        load_dotenv()
        env = dict(os.environ)
    panel = [m.strip() for m in env.get("BEDROCK_PANEL_MODELS", "").split(",") if m.strip()]
    return Config(
        region=env.get("AWS_REGION", "us-east-1"),
        roles={
            "generator": env.get("BEDROCK_GENERATOR_MODEL", ""),
            "inloop_judge": env.get("BEDROCK_INLOOP_JUDGE_MODEL", ""),
        },
        panel_models=panel,
        exa_key=env.get("EXA_API_KEY", ""),
        tavily_key=env.get("TAVILY_API_KEY", ""),
        semantic_scholar_key=env.get("SEMANTIC_SCHOLAR_API_KEY", ""),
        perplexity_key=env.get("PERPLEXITY_API_KEY", ""),
        wandb_key=env.get("WANDB_API_KEY", ""),
    )
