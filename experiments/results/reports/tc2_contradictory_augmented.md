# Research Report
**Query:** Is chain-of-thought prompting an effective reasoning strategy for LLMs, or does it primarily improve output formatting? The literature disagrees—find the real fault lines and explain what accounts for the conflicting results. Include an architecture diagram of the relevant pipeline or process.

## Summary
The effectiveness of chain-of-thought (CoT) prompting for large language models (LLMs) is a topic of debate in the literature. While some studies show that CoT improves reasoning accuracy, others demonstrate its limitations [c11]. This report examines the fault lines in the literature and explains the conflicting results.


## Architecture

```mermaid
graph LR;
    subgraph Input Processing;
        A[Input Query] --> B[CoT Demonstrations with Reasoning Steps];
    end;
    subgraph LLM Processing;
        B --> C[LLM Generates Intermediate Rationales];
        C --> D[Output Formatting with Step-by-Step Rationales];
    end;
    subgraph Output;
        D --> E[Final Output with Rationales];
    end;
    subgraph Influencing Factors;
        F[Relevance to Input Query] -.-> C;
        G[Correct Ordering of Reasoning Steps] -.-> C;
        H[Model Size (~100B parameters)] -.-> C;
        I[Task Type (e.g., math, coding, knowledge)] -.-> C;
    end;
```

## Effectiveness of CoT Prompting
CoT prompting is a method that encourages LLMs to generate intermediate rationales for solving a problem by providing a series of reasoning steps in the demonstrations [c0]. It enables LLMs to decompose multi-step problems into intermediate steps, which can be solved individually [c1]. The benefits of CoT prompting are more pronounced in larger models, typically those with around 100B parameters [c5].

## Factors Influencing CoT Effectiveness
The validity of the reasoning in the prompting examples has a limited impact on the performance of CoT prompting [c2]. However, relevance to the input query and correct ordering of the reasoning steps are key factors in the effectiveness of CoT prompting [c3]. CoT prompting provides an interpretable window into the behavior of the model, suggesting how it might have arrived at a particular answer [c4].

## Conflicting Results
Some studies have found that CoT is highly effective in solving complex reasoning tasks such as mathematics and coding [c12]. However, other works have shown that CoT brings only limited improvements in knowledge and commonsense reasoning tasks and may even harm the model's original performance [c13]. The effectiveness of CoT prompting varies greatly depending on the type of task and model [c18].

## Role of CoT in Output Formatting
CoT prompting improves LLMs' output formatting by regularizing the LLM to generate rationales that look step-by-step [c6]. The provided reasoning steps in CoT demonstrations serve more as the role of an output format/space that regularizes the LLM to generate rationales that look step-by-step [c21].

## Architecture Diagram
The relevant pipeline or process for CoT prompting involves the following steps:
1. Input query
2. CoT demonstrations with reasoning steps
3. LLM generates intermediate rationales
4. Output with step-by-step rationales

```markdown
graph LR;
    A[Input Query] --> B[CoT Demonstrations];
    B --> C[LLM Generates Intermediate Rationales];
    C --> D[Output with Step-by-Step Rationales];
```

## Conclusion
The conflicting results in the literature can be attributed to the task-dependent effectiveness of CoT prompting and the varying dynamics of different model types. While CoT prompting can improve reasoning accuracy in certain tasks, its benefits are limited in others. The faithfulness of CoT explanations is also a concern, as they may not accurately represent the reasoning process behind the model's decision [c15].


---

## Detailed Citation Results
| # | Claim | Sources |
|---|---|---|
| c0 | Chain-of-thought (CoT) prompting is a method that encourages large language models (LLMs) to generate intermediate rationales for solving a problem by providing a series of reasoning steps in the demonstrations. | https://arxiv.org/pdf/2212.10001, https://arxiv.org/pdf/2309.15402v2 |
| c1 | CoT prompting enables LLMs to decompose multi-step problems into intermediate steps, which can be solved individually. | https://proceedings.neurips.cc/paper_files/paper/2022/file/9d5609613524ecf4f15af0f7b31abca4-Paper-Conference.pdf, https://research.google/blog/language-models-perform-reasoning-via-chain-of-thought/ |
| c2 | The validity of the reasoning in the prompting examples has a limited impact on the performance of CoT prompting. | https://arxiv.org/pdf/2212.10001 |
| c3 | Relevance to the input query and correct ordering of the reasoning steps are key factors in the effectiveness of CoT prompting. | https://arxiv.org/pdf/2212.10001 |
| c4 | CoT prompting provides an interpretable window into the behavior of the model, suggesting how it might have arrived at a particular answer. | https://proceedings.neurips.cc/paper_files/paper/2022/file/9d5609613524ecf4f15af0f7b31abca4-Paper-Conference.pdf |
| c5 | The benefits of CoT prompting are more pronounced in larger models, typically those with around 100B parameters. | https://research.google/blog/language-models-perform-reasoning-via-chain-of-thought/ |
| c6 | Chain-of-thought prompting improves LLMs' output formatting by regularizing the LLM to generate rationales that look step-by-step. | https://arxiv.org/pdf/2212.10001 |
| c7 | Chain-of-thought prompting can introduce inconsistency in answers for non-reasoning models. | https://gail.wharton.upenn.edu/research-and-insights/tech-report-chain-of-thought/ |
| c8 | For models with built-in reasoning capabilities, chain-of-thought prompting produced minimal benefits in terms of accuracy. | https://gail.wharton.upenn.edu/research-and-insights/tech-report-chain-of-thought/ |
| c9 | Chain-of-thought prompting outperforms standard prompting on arithmetic, commonsense, and symbolic reasoning benchmarks. | https://arxiv.org/abs/2201.11903 |
| c10 | The provided reasoning steps in chain-of-thought prompting serve more as the role of an output format/space. | https://arxiv.org/pdf/2212.10001 |
| c11 | The literature disagrees on the effectiveness of chain-of-thought (CoT) prompting for LLMs, with some studies showing it improves reasoning accuracy and others demonstrating its limitations. | https://aclanthology.org/2025.findings-acl.560.pdf |
| c12 | Some studies have found that CoT is highly effective in solving complex reasoning tasks such as mathematics and coding. | https://aclanthology.org/2025.findings-acl.560.pdf |
| c13 | Other works have shown that CoT brings only limited improvements in knowledge and commonsense reasoning tasks and may even harm the model's original performance. | https://aclanthology.org/2025.findings-acl.560.pdf |
| c14 | CoT's effectiveness is task-dependent, with significant benefits observed in symbolic tasks that require tracing and computation. | https://par.nsf.gov/servlets/purl/10631084 |
| c15 | The faithfulness of CoT explanations is a concern, as they may not accurately represent the reasoning process behind the model's decision. | https://aclanthology.org/2025.emnlp-main.1516.pdf, https://aclanthology.org/2025.findings-acl.560.pdf |
| c16 | Some research suggests that CoT operates as a dual-process mechanism, combining explicit and implicit reasoning, but this mechanism is compromised due to LLMs' limited ability to infer accurate patterns explicitly and increased contextual distance. | https://arxiv.org/html/2504.05081v2 |
| c17 | Even when CoT explanations are logically correct, they can still be unfaithful by omitting key reasons for the model's final answer. | https://link.springer.com/chapter/10.1007/978-3-032-21300-6_53 |
| c18 | The effectiveness of Chain-of-Thought (CoT) prompting varies greatly depending on the type of task and model. | https://arxiv.org/abs/2506.07142v1 |
| c19 | For non-reasoning models, CoT generally improves average performance by a small amount. | https://arxiv.org/abs/2506.07142v1 |
| c20 | CoT can introduce more variability in answers and sometimes trigger occasional errors in questions the model would otherwise get right. | https://arxiv.org/abs/2506.07142v1 |
| c21 | The provided reasoning steps in CoT demonstrations serve more as the role of an output format/space that regularizes the LLM to generate rationales that look step-by-step. | https://arxiv.org/pdf/2212.10001 |
| c22 | LLMs have already gained complex reasoning ability from pretraining, and CoT prompting has limited impact on their reasoning. | https://arxiv.org/pdf/2212.10001 |
| c23 | The particular phrasing of CoT may be responsible for the boost conveyed by CoT, rather than the content of the CoT itself. | 43677584289, https://aclanthology.org/2025.emnlp-main.1516.pdf |
| c24 | Different model types (instruction-tuned, reasoning, and distilled-reasoning models) exhibit different dynamics and faithfulness in CoT reasoning. | https://aclanthology.org/2025.emnlp-main.1516.pdf |
| c25 | Enhancing CoT's faithfulness can improve its effectiveness. | https://aclanthology.org/2025.findings-acl.560.pdf |

## Sources
- [https://arxiv.org/pdf/2212.10001] [2212.10001] Towards Understanding Chain-of-Thought Prompting: An Empirical Study of What Matters
- [https://arxiv.org/pdf/2309.15402v2] A Survey of Chain of Thought Reasoning: Advances, Frontiers and Future
- [https://proceedings.neurips.cc/paper_files/paper/2022/file/9d5609613524ecf4f15af0f7b31abca4-Paper-Conference.pdf] Chain-of-Thought Prompting Elicits Reasoning in Large Language Models
- [https://aclanthology.org/2023.findings-emnlp.101.pdf] What makes Chain-of-Thought Prompting Effective? A Counterfactual Study
- [https://research.google/blog/language-models-perform-reasoning-via-chain-of-thought/] Language Models Perform Reasoning via Chain of Thought
- [https://gail.wharton.upenn.edu/research-and-insights/tech-report-chain-of-thought/] Technical Report: The Decreasing Value of Chain of Thought in Prompting - Wharton Generative AI Labs
- [https://arxiv.org/abs/2201.11903] [2201.11903] Chain-of-Thought Prompting Elicits Reasoning in Large Language Models
- [https://aclanthology.org/2025.findings-acl.560.pdf] Towards Better Chain-of-Thought: A Reflection on Effectiveness and Faithfulness
- [https://par.nsf.gov/servlets/purl/10631084] TO OR NOT TO CHAIN-OF-THOUGHT HELPS MAINLY ON MATH AND SYMBOLIC REASONING
- [https://arxiv.org/html/2504.05081v2] The Curse of CoT: On the Limitations of Chain-of-Thought in In-Context Learning
- [https://aclanthology.org/2025.emnlp-main.1516.pdf] Analysing Chain of Thought Dynamics: Active Guidance or Unfaithful Post-hoc Rationalisation?
- [https://link.springer.com/chapter/10.1007/978-3-032-21300-6_53] Correct but Incomplete: Why Chain-of-Thought Cannot Currently Support Auditable Reasoning | Springer Nature Link
- [https://arxiv.org/abs/2506.07142v1] [2506.07142v1] Prompting Science Report 2: The Decreasing Value of Chain of Thought in Prompting
- [43677584289] Measuring Faithfulness in Chain-of-Thought Reasoning