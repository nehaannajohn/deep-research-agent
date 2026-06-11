# Verifier comparison — 20-example stratified sample

conf = self-consistency agreement (solos, /5) or cross-model agreement (ensemble, /3)

| idx | intended | sonnet (pred·conf) | mistral (pred·conf) | nova (pred·conf) | ensemble (pred·conf) | claim |
|---|---|---|---|---|---|---|
| 0 | supported | supported·1.0 | supported·1.0 | supported·1.0 | supported·1.0 | Fine-tuning large language models (LLMs) on datasets overlapping with  |
| 1 | refuted | refuted·1.0 | refuted·1.0 | refuted·1.0 | refuted·1.0 | Fine-tuning large language models (LLMs) on datasets overlapping with  |
| 2 | insufficient | insufficient·1.0 | insufficient·1.0 | insufficient·1.0 | insufficient·1.0 | Fine-tuning large language models (LLMs) on datasets overlapping with  |
| 3 | contested | contested·1.0 | contested·1.0 | contested·1.0 | contested·1.0 | Fine-tuning large language models (LLMs) on datasets overlapping with  |
| 4 | supported | supported·1.0 | supported·1.0 | supported·1.0 | supported·1.0 | Fine-tuning on generated data may introduce significant privacy danger |
| 5 | refuted | refuted·1.0 | refuted·1.0 | refuted·0.6 | refuted·1.0 | Fine-tuning on generated data is unlikely to introduce significant pri |
| 6 | insufficient | insufficient·1.0 | supported·1.0 | insufficient·1.0 | insufficient·0.6666666666666666 | Fine-tuning on generated data may introduce significant privacy danger |
| 7 | contested | contested·1.0 | contested·0.6 | contested·1.0 | contested·1.0 | Fine-tuning on generated data may introduce significant privacy danger |
| 8 | supported | supported·1.0 | supported·1.0 | supported·1.0 | supported·1.0 | LLM-generated data is potentially more susceptible to privacy attacks  |
| 9 | refuted | refuted·1.0 | refuted·1.0 | refuted·1.0 | refuted·1.0 | LLM-generated data is potentially less susceptible to privacy attacks  |
| 10 | insufficient | insufficient·1.0 | supported·1.0 | insufficient·1.0 | insufficient·0.6666666666666666 | LLM-generated data is potentially more susceptible to privacy attacks  |
| 11 | supported | supported·1.0 | supported·1.0 | supported·1.0 | supported·1.0 | Recursive training on synthetic data leads to a 'self-consuming' loop  |
| 12 | refuted | refuted·1.0 | refuted·1.0 | refuted·1.0 | refuted·1.0 | Recursive training on synthetic data leads to a 'self-consuming' loop  |
| 13 | insufficient | insufficient·1.0 | supported·1.0 | insufficient·1.0 | insufficient·0.6666666666666666 | Recursive training on synthetic data leads to a 'self-consuming' loop  |
| 14 | contested | contested·1.0 | contested·1.0 | contested·1.0 | contested·1.0 | Recursive training on synthetic data leads to a 'self-consuming' loop  |
| 15 | supported | supported·1.0 | supported·1.0 | supported·1.0 | supported·1.0 | Chain-of-thought prompting is a technique that instructs large languag |
| 16 | refuted | refuted·1.0 | refuted·1.0 | refuted·1.0 | refuted·1.0 | Chain-of-thought prompting is a technique that fails to improve the pe |
| 17 | insufficient | insufficient·1.0 | insufficient·1.0 | insufficient·1.0 | insufficient·1.0 | Chain-of-thought prompting is a technique that instructs large languag |
| 21 | contested | contested·1.0 | contested·1.0 | contested·1.0 | contested·1.0 | Chain-of-thought prompting enables complex reasoning capabilities thro |
| 25 | contested | contested·1.0 | contested·1.0 | contested·1.0 | contested·1.0 | Chain-of-thought prompting allows models to decompose multi-step probl |
