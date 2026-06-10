from dra.llm.bedrock import BedrockChat


class FakeClient:
    def __init__(self, text="hello-from-fake"):
        self.text = text
        self.last = None

    def converse(self, **kwargs):
        self.last = kwargs
        return {"output": {"message": {"content": [{"text": self.text}]}}}


def test_complete_returns_text_and_builds_request():
    fc = FakeClient()
    chat = BedrockChat("anthropic.claude-x", client=fc)
    out = chat.complete("hi", temperature=0.0)
    assert out == "hello-from-fake"
    assert fc.last["modelId"] == "anthropic.claude-x"
    assert fc.last["messages"][0]["content"][0]["text"] == "hi"


def test_complete_json_parses():
    chat = BedrockChat("m", client=FakeClient(text='{"a": 1}'))
    assert chat.complete_json("give json") == {"a": 1}


def test_complete_skips_reasoning_block():
    class ReasoningClient:
        def converse(self, **kwargs):
            return {"output": {"message": {"content": [
                {"reasoningContent": {"reasoningText": {"text": "thinking..."}}},
                {"text": "final answer"},
            ]}}}

    assert BedrockChat("m", client=ReasoningClient()).complete("hi") == "final answer"


def test_complete_retries_without_temperature_when_rejected():
    class TempRejectClient:
        def __init__(self):
            self.calls = []

        def converse(self, **kwargs):
            self.calls.append(kwargs)
            if "temperature" in kwargs["inferenceConfig"]:
                raise RuntimeError("ValidationException: `temperature` is deprecated for this model.")
            return {"output": {"message": {"content": [{"text": "OK"}]}}}

    c = TempRejectClient()
    out = BedrockChat("opus", client=c).complete("hi", temperature=0.0)
    assert out == "OK"
    assert len(c.calls) == 2
    assert "temperature" in c.calls[0]["inferenceConfig"]
    assert "temperature" not in c.calls[1]["inferenceConfig"]
