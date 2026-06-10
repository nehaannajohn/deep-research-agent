import pytest

from dra.config import family, load_config


def test_roles_and_panel_parsed():
    env = {
        "AWS_REGION": "us-west-2",
        "BEDROCK_GENERATOR_MODEL": "anthropic.claude-3-5-sonnet-20241022-v2:0",
        "BEDROCK_INLOOP_JUDGE_MODEL": "meta.llama3-1-70b-instruct-v1:0",
        "BEDROCK_PANEL_MODELS": "anthropic.claude-x, meta.llama-y , mistral.large-z",
    }
    cfg = load_config(env)
    assert cfg.region == "us-west-2"
    assert cfg.roles["generator"].startswith("anthropic.")
    assert len(cfg.panel_models) == 3
    cfg.assert_independence()  # different families -> no raise


def test_independence_violation_raises():
    env = {
        "BEDROCK_GENERATOR_MODEL": "anthropic.claude-a",
        "BEDROCK_INLOOP_JUDGE_MODEL": "anthropic.claude-b",
    }
    with pytest.raises(ValueError):
        load_config(env).assert_independence()


def test_drop_empty_aws_env():
    from dra.config import _drop_empty_aws_env

    env = {"AWS_ACCESS_KEY_ID": "", "AWS_SECRET_ACCESS_KEY": "",
           "AWS_PROFILE": "Arenal-science", "AWS_SESSION_TOKEN": "tok"}
    _drop_empty_aws_env(env)
    assert "AWS_ACCESS_KEY_ID" not in env  # empty -> dropped
    assert "AWS_SECRET_ACCESS_KEY" not in env  # empty -> dropped
    assert env["AWS_PROFILE"] == "Arenal-science"  # non-empty -> kept
    assert env["AWS_SESSION_TOKEN"] == "tok"  # non-empty -> kept


def test_family():
    assert family("meta.llama3-1-70b-instruct-v1:0") == "meta"
    assert family("") == ""


def test_family_strips_inference_profile_scope():
    assert family("us.meta.llama4-maverick-17b-instruct-v1:0") == "meta"
    assert family("global.anthropic.claude-opus-4-8") == "anthropic"
    assert family("mistral.mistral-large-3-675b-instruct") == "mistral"
    assert family("openai.gpt-oss-120b-1:0") == "openai"
