# Research Report
**Query:** Is chain-of-thought prompting an effective reasoning strategy for LLMs, or does it primarily improve output formatting? The literature disagrees—find the real fault lines and explain what accounts for the conflicting results.

## Summary
Chain-of-thought (CoT) prompting is a technique used to improve the reasoning capabilities of large language models (LLMs) by generating intermediate steps before delivering final answers [c0]. The effectiveness of CoT prompting is a topic of debate, with some studies suggesting it improves reasoning, while others argue it primarily enhances output formatting. This report examines the fault lines in the literature and explains the conflicting results.

## Mechanism of CoT Prompting
CoT prompting operates through zero-shot cues and few-shot exemplars, breaking down complex problems into sequential logic [c2]. It involves restating the problem, decomposing it into sub-steps, computing or justifying each sub-result, and synthesizing the final answer [c4]. This process simulates human-like reasoning by generating manageable, intermediate steps [c5].

## Effectiveness of CoT Prompting
CoT prompting significantly boosts performance on multi-step tasks such as arithmetic, commonsense reasoning, and symbolic logic [c3]. It improves reasoning in LLMs primarily on tasks involving math or logic [c6]. However, its effectiveness varies greatly depending on the type of task and model [c25]. For models with explicit reasoning capabilities, CoT prompting often results in marginal gains in answer accuracy [c26].

## Role of Output Formatting
Some studies suggest that CoT prompting primarily improves output formatting, serving as a decoding space pruner that guides output generation [c12][c14]. The provided reasoning steps may regularize the LLM to generate rationales that look step-by-step, rather than facilitating actual reasoning [c13]. The format of CoT prompting can significantly impact its effectiveness, with format changes easily affecting CoT reasoning [c19].

## Conflicting Results
The conflicting results in the literature can be attributed to the varying effectiveness of CoT prompting across different tasks and models. While CoT prompting improves performance on certain tasks, its benefits are marginal for models with explicit reasoning capabilities [c26]. Additionally, the validity of reasoning in the prompting examples has a limited impact on the performance of CoT prompting [c10].

## Conclusion
The effectiveness of CoT prompting depends on the task and model used. While it improves reasoning in LLMs on certain tasks, its primary benefit may be in enhancing output formatting. The format of CoT prompting plays a crucial role in its effectiveness, and its benefits are task-dependent [c25].

---

## Detailed Citation Results
| # | Claim | Sources |
|---|---|---|
| c0 | Chain-of-thought (CoT) prompting is a prompt engineering technique that instructs large language models to show their reasoning by generating intermediate steps before delivering final answers. | https://aws.amazon.com/what-is/chain-of-thought-prompting/, https://www.ibm.com/think/topics/chain-of-thoughts |
| c1 | CoT prompting works with existing models without modifying their weights or architecture. | https://aws.amazon.com/what-is/chain-of-thought-prompting/ |
| c2 | The technique operates through two core mechanisms: zero-shot cues and few-shot exemplars. | https://aws.amazon.com/what-is/chain-of-thought-prompting/ |
| c3 | CoT prompting breaks complex problems into sequential logic and significantly boosts performance on multi-step tasks such as arithmetic, commonsense reasoning, and symbolic logic. | https://aws.amazon.com/what-is/chain-of-thought-prompting/, https://research.google/blog/language-models-perform-reasoning-via-chain-of-thought/, https://www.ibm.com/think/topics/chain-of-thoughts |
| c4 | The reasoning process in CoT involves restating the problem, decomposing it into sub-steps, computing or justifying each sub-result, and synthesizing the final answer. | https://aws.amazon.com/what-is/chain-of-thought-prompting/ |
| c5 | CoT prompting simulates human-like reasoning processes by breaking down elaborate problems into manageable, intermediate steps. | https://www.ibm.com/think/topics/chain-of-thoughts |
| c6 | Chain-of-thought prompting improves reasoning in LLMs primarily on tasks involving math or logic. | 49338718303 |
| c7 | Chain-of-thought prompting improves performance on a range of arithmetic, commonsense, and symbolic reasoning tasks. | https://proceedings.neurips.cc/paper_files/paper/2022/file/9d5609613524ecf4f15af0f7b31abca4-Paper-Conference.pdf |
| c8 | The effectiveness of chain-of-thought prompting may stem from its ability to efficiently convey task understanding to the LLM. | https://aclanthology.org/2023.findings-emnlp.101.pdf |
| c9 | Chain-of-thought prompting can achieve high performance even with invalid demonstrations, suggesting that valid reasoning is not required. | https://arxiv.org/pdf/2212.10001 |
| c10 | The validity of reasoning in the prompting examples matters only a small portion to the performance of chain-of-thought prompting. | https://arxiv.org/pdf/2212.10001 |
| c11 | Improving the faithfulness of chain-of-thought prompting can lead to enhancements in its effectiveness. | https://aclanthology.org/2025.findings-acl.560.pdf |
| c12 | Chain-of-thought prompting primarily improves output formatting in LLMs. | https://arxiv.org/html/2507.20758v2, https://arxiv.org/pdf/2212.10001 |
| c13 | The provided reasoning steps in chain-of-thought prompting serve more as the role of an output format/space that regularizes the LLM to generate rationales that look step-by-step. | https://arxiv.org/pdf/2212.10001 |
| c14 | CoT may serve as a decoding space pruner, leveraging answer templates to guide output generation. | https://arxiv.org/html/2507.20758v2 |
| c15 | CoT prompting reshapes model outputs by guiding the generation of intermediate reasoning steps before the final answer, yielding more structured, task-relevant outputs. | https://arxiv.org/html/2507.20758v2 |
| c16 | The effectiveness of CoT may stem from its ability to efficiently convey task understanding to the LLM. | https://aclanthology.org/2023.findings-emnlp.101.pdf |
| c17 | Format matters more than content or logical validity in CoT effectiveness. | https://arxiv.org/html/2507.20758v2 |
| c18 | CoT primarily helps with the execution step that performs computation and manipulation. | https://arxiv.org/pdf/2409.12183 |
| c19 | CoT reasoning can be easily affected by format changes. | https://arxiv.org/html/2508.01191v3 |
| c25 | The effectiveness of chain-of-thought prompting varies greatly depending on the type of task and model. | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5285532 |
| c26 | For models designed with explicit reasoning capabilities, chain-of-thought prompting often results in only marginal gains in answer accuracy. | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5285532 |
| c27 | Chain-of-thought prompting does not always improve performance for soft-reasoning tasks such as commonsense reasoning. | https://aclanthology.org/2025.emnlp-main.1516.pdf |
| c28 | The primary strength of chain-of-thought prompting lies in its ability to succinctly express the necessary tasks, thereby guiding the models more effectively. | https://openreview.net/forum?id=va7nzRsbA4 |
| c29 | The intermediate steps in chain-of-thought prompting may not necessarily facilitate learning how to solve a task, but instead efficiently convey task understanding to the model. | https://openreview.net/forum?id=va7nzRsbA4 |

## Sources
- [https://aws.amazon.com/what-is/chain-of-thought-prompting/] What Is Chain-of-Thought Prompting? - Chain-of-Thought Prompting Explained - AWS
- [https://www.ibm.com/think/topics/chain-of-thoughts] What is chain of thought (CoT) prompting? | IBM
- [https://research.google/blog/language-models-perform-reasoning-via-chain-of-thought/] Language Models Perform Reasoning via Chain of Thought
- [https://www.promptingguide.ai/techniques/cot] Chain-of-Thought Prompting | Prompt Engineering Guide<!-- -->
- [https://arxiv.org/abs/2201.11903] [2201.11903] Chain-of-Thought Prompting Elicits Reasoning in Large Language Models
- [49338718303] To CoT or not to CoT? Chain-of-thought helps mainly on math and symbolic reasoning
- [https://proceedings.neurips.cc/paper_files/paper/2022/file/9d5609613524ecf4f15af0f7b31abca4-Paper-Conference.pdf] Chain-of-Thought Prompting Elicits Reasoning in Large Language Models
- [https://aclanthology.org/2023.findings-emnlp.101.pdf] What makes Chain-of-Thought Prompting Effective? A Counterfactual Study
- [https://arxiv.org/pdf/2212.10001] [2212.10001] Towards Understanding Chain-of-Thought Prompting: An Empirical Study of What Matters
- [https://aclanthology.org/2025.findings-acl.560.pdf] Towards Better Chain-of-Thought: A Reflection on Effectiveness and Faithfulness
- [https://arxiv.org/html/2507.20758v2] How Chain-of-Thought Works? Tracing Information Flow from Decoding, Projection, and Activation
- [https://arxiv.org/pdf/2409.12183] https://arxiv.org/pdf/2409.12183
- [https://arxiv.org/html/2508.01191v3] Is Chain-of-Thought Reasoning of LLMs a Mirage? A Data Distribution Lens
- [https://openreview.net/pdf?id=w6nlcS8Kkn] TO OR NOT TO CHAIN-OF-THOUGHT HELPS MAINLY ON MATH AND SYMBOLIC REASONING
- [https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5285532] Prompting Science Report 2: The Decreasing Value of Chain of Thought in Prompting
- [https://aclanthology.org/2025.emnlp-main.1516.pdf] Analysing Chain of Thought Dynamics: Active Guidance or Unfaithful Post-hoc Rationalisation?
- [https://openreview.net/forum?id=va7nzRsbA4] What Makes Chain-of-Thought Prompting Effective? A Counterfactual Study | OpenReview