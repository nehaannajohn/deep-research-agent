"""DRA-Bench gold synthesizer (Phase G).

`synth_prompts` builds the 250 typed prompts (5 types x ~50); `fable_reference`
turns a Fable reference report into a `GradableReport` scored on the same axes.
The pure assembly is fake-tested; the live LLM/Fable calls are `# pragma: no
cover`.
"""
