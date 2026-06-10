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
