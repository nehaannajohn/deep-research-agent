from dra.router import route


class FakeLLM:
    def __init__(self, answer):
        self.answer = answer

    def complete(self, prompt):
        return self.answer


def test_route_academic():
    assert route("scaling laws for transformer language models", FakeLLM("academic")) == "academic"


def test_route_web_and_default():
    assert route("best coffee in Seattle", FakeLLM("web")) == "web"
    assert route("x", FakeLLM("I think general knowledge")) == "web"  # default when unclear
