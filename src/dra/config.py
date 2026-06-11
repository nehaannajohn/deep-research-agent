"""Environment + per-role model assignment.

Model independence is a design requirement: the generator, the in-loop judge
verifier, and the evaluation panel must be different model *families* so biases
don't correlate. `assert_independence()` enforces the generator/in-loop split.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from dotenv import load_dotenv


# Inference-profile ids carry a region-scope prefix (us./global./eu./apac.)
# before the provider; bare on-demand ids start with the provider.
_SCOPES = {"us", "global", "eu", "apac", "us-gov"}


def family(model_id: str) -> str:
    """Provider family of a model / inference-profile id (region-scope prefix stripped)."""
    if not model_id:
        return ""
    parts = model_id.split(".")
    if parts[0] in _SCOPES and len(parts) > 1:
        return parts[1]
    return parts[0]


@dataclass
class Config:
    region: str
    roles: dict
    panel_models: list
    verifier_models: list = field(default_factory=list)
    exa_key: str = ""
    tavily_key: str = ""
    semantic_scholar_key: str = ""
    perplexity_key: str = ""
    wandb_key: str = ""
    retrieval_cache_enabled: bool = True
    retrieval_cache_ttl_s: int = 259200  # 3 days
    retrieval_cache_dir: str = "data/cache/retrieval"

    def assert_independence(self) -> None:
        g = family(self.roles.get("generator", ""))
        j = family(self.roles.get("inloop_judge", ""))
        if g and j and g == j:
            raise ValueError(
                f"generator and in-loop judge must be different model families (both '{g}')"
            )


def _env_bool(env, key: str, default: bool) -> bool:
    v = env.get(key)
    if v is None:
        return default
    return v.strip().lower() not in ("0", "false", "no", "")


def _drop_empty_aws_env(environ) -> None:
    """Empty AWS_* values from a template .env poison botocore's credential chain
    (it prefers env-var creds over the named profile -> InvalidClientTokenId).
    Remove the empties so AWS_PROFILE / the default chain resolves cleanly."""
    for k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "AWS_PROFILE"):
        if environ.get(k, None) == "":
            environ.pop(k, None)


def load_config(env: "dict | None" = None) -> Config:
    if env is None:
        load_dotenv()
        _drop_empty_aws_env(os.environ)
        env = dict(os.environ)
    panel = [m.strip() for m in env.get("BEDROCK_PANEL_MODELS", "").split(",") if m.strip()]
    verifiers = [m.strip() for m in env.get("BEDROCK_VERIFIER_MODELS", "").split(",") if m.strip()]
    return Config(
        region=env.get("AWS_REGION", "us-east-1"),
        roles={
            "generator": env.get("BEDROCK_GENERATOR_MODEL", ""),
            "inloop_judge": env.get("BEDROCK_INLOOP_JUDGE_MODEL", ""),
        },
        panel_models=panel,
        verifier_models=verifiers,
        exa_key=env.get("EXA_API_KEY", ""),
        tavily_key=env.get("TAVILY_API_KEY", ""),
        semantic_scholar_key=env.get("SEMANTIC_SCHOLAR_API_KEY", ""),
        perplexity_key=env.get("PERPLEXITY_API_KEY", ""),
        wandb_key=env.get("WANDB_API_KEY", ""),
        retrieval_cache_enabled=_env_bool(env, "DRA_RETRIEVAL_CACHE", True),
        retrieval_cache_ttl_s=int(env.get("DRA_RETRIEVAL_CACHE_TTL", "259200")),
        retrieval_cache_dir=env.get("DRA_RETRIEVAL_CACHE_DIR", "data/cache/retrieval"),
    )
