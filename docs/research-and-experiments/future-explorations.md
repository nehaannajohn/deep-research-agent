# Future Explorations (not part of the current design)

A running list of directions **outside** the current MVP design. Time permitting, we'll use this file to decide which directions to explore next. Adding an idea here is not a commitment — it's a parking lot for candidates to prioritize later.

Each entry: what it is, why it might be worth it, and rough scope.

---

## 1. DSPy for prompt optimization
**What.** Use [DSPy](https://github.com/stanfordnlp/dspy) to programmatically optimize the prompts/signatures in the pipeline (planner/decomposition, claim extraction, verifier, generator) instead of hand-tuning prompt strings.
**Why it might be worth it.** Our prompts are currently hand-written and tuned ad hoc; DSPy could compile prompts/few-shots against our eval metrics (grounding, atomicity, coverage) and reduce manual prompt iteration while improving consistency across models.
**Rough scope.** Wrap a stage (start with claim extraction or the verifier) as a DSPy module, wire our judged metrics as the optimization target, compare optimized vs. hand-written prompts on the existing test cases.

---

## 2. Claude Fable for experiments
**What.** Explore using [Claude Fable](https://www.anthropic.com/) (Fable 5) as a model for our experiments — e.g. as a generator, in-loop verifier, or evaluation-panel member — and benchmark it against the current Bedrock roster (Llama 4 Maverick generator, Mistral Large 3 verifier, the judge panel).
**Why it might be worth it.** Our roles currently draw from a fixed set of Bedrock families; adding Fable 5 widens the candidate pool and could improve grounding/atomicity or panel diversity, while keeping model independence (generator ≠ verifier ≠ judge) intact.
**Rough scope.** Wire Fable 5 in behind the existing injectable client interface, slot it into one role at a time, and compare against the incumbent on our judged metrics (grounding, atomicity, coverage) using the existing experiment scripts.

---

## 3. RL-trained research policy via verifier-supervised distillation

**What.** Train a *single, smaller* policy model that absorbs the behavior of the current multi-model pipeline (decompose → retrieve → claim-extract → verify → adaptive-retrieve), using the **existing verifier as the supervision signal**. The POC route is **rejection-sampling distillation**, not online RL: the current pipeline (large Bedrock models) generates research trajectories, the verifier filters/scores them, and the survivors become SFT targets for a small open-weights policy. The full online-RL version (verifier as a live process reward, GRPO) is the labeled extension, not the POC.

**Why it might be worth it.** Three wins: (1) **cost** — replace several large frozen-model calls + an iterative loop with one small policy; (2) **amortize inference-time compute into weights** — the adaptive loop runs once at data-gen (teacher) and the student learns to land on the converged answer with far fewer iterations; (3) **post-training story** — demonstrates real post-training judgment while reusing the verifier we already built as designed. It also yields clean ablations that *measure* the cost/quality tradeoff rather than asserting it.

**Why this is a small-timeframe POC (not multi-month).** Distillation sidesteps the two expensive parts of online RL: the *data problem* disappears (our pipeline IS the data generator), and the *offline-retrieval-environment / reward-hacking* problems evaporate (search is called once per training example at data-gen, not thousands of times in a hot training loop; the policy never optimizes against the verifier online, so there is no gaming loop). Estimated effort: **days to ~2 weeks**.

---

### 3.1 Design — data recipe (the core of the POC)

```
queries (HotpotQA / ASQA / DRA-Bench seeds, thousands — queries only, no gold answers needed)
  → run existing pipeline (teacher)            # produces full agentic trajectories
  → verifier scores/filters trajectories       # OFFLINE filter, not a live reward
  → best-of-N selection per query              # keep verifier-best of N samples
  → path-compress the surviving trajectories   # drop wasted iterations (see 3.2)
  → serialize to single-policy trajectory format
  → SFT / LoRA a small open-weights policy (7–8B)
  → evaluate on the existing harness
```

**Verifier as offline *filter*, not online reward.** For the POC the verifier is a data-quality gate: keep high-grounding trajectories, drop weak ones. This is what keeps the timeline small — no GRPO, no rollout infra, no reward-hacking iteration loop.

**Best-of-N to beat the *average* teacher.** Sample N trajectories per query, keep only the verifier-best. The student then learns the **upper envelope** of the teacher rather than its mean (STaR/RFT). Pure distillation still ceilings at teacher capability; best-of-N buys modest headroom above the average teacher and gives a clean ablation.

### 3.2 Trajectory compression (the "skip the wasted iterations" idea)

Do **not** train on `query → final claims` with retrieval discarded — that teaches the model to fabricate citations and breaks the grounding invariant (citations are retrieved passages, not model output). Instead, **path-compress the successful trajectory**: keep the `(winning sub-query → retrieved passages → verified claim)` tuples and drop the failed reformulation iterations, so the *winning* sub-queries appear as if issued first. The teacher fumbled for 3 iterations to find the right phrasing; the student is trained to issue it immediately. This also fixes credit assignment — the good sub-queries are now in the target as tokens to imitate.

**Caveat — don't teleport dependency-bearing queries.** Compression is safe when iterations were wasted on *bad phrasing* (the query text was all that mattered). It is **not** safe when a late query was only askable because an earlier retrieval surfaced an entity/term (genuine multi-hop). Preserve legitimate information-dependency chains; compress only the redundant fumbling. Compression is selective.

### 3.3 Keep the verifier + adaptive loop as an inference-time fallback

The adaptive loop is also the correctness backstop and the transparency guarantee (ship `insufficient` rather than fabricate). Do **not** delete it. Target behavior: **one pass in the common case, escalate only when one-shot grounding is weak.** The student internalizes good first-shot retrieval so most queries resolve immediately; the verifier still runs at inference and the loop still fires for the hard ones. This is *learned test-time compute* achieved via distillation rather than online RL — the cost win without surrendering the grounding guarantee.

### 3.4 Ablations (these make the POC a result, not a demo)

| Ablation | Isolates | Metric |
|---|---|---|
| Unfiltered vs **verifier-filtered** distillation | value of the verifier as supervision | grounding rate, hallucination rate |
| **Compressed** vs full-iterative trajectory targets | the cost win | iterations-to-converge, search-calls/query **at fixed grounding** |
| Small distilled policy vs teacher pipeline | capability retained per cost | rubric axes + cost/latency |

### 3.5 What it proves / does not prove

- **Proves:** a small policy can absorb the pipeline's grounded-research behavior; the verifier is usable as a supervision signal; iteration/cost can be reduced at fixed grounding.
- **Does not prove:** that training pushes *past* the prompting ceiling. Distillation ceilings at the teacher (best-of-N buys only modest headroom). Exceeding the teacher requires the online-RL extension below. State this as the scoped limitation.

### 3.6 Components needed & effort

Mostly reuse. Net-new for the POC is small:
- **Trajectory serializer** — flatten the LangGraph multi-step run into one trainable sequence (reasoning → search query → observation → … → claims+citations). *The main new piece of work.*
- **Filtering + best-of-N + compression pass** over generated trajectories (uses the existing verifier).
- **A small trainable policy + a single SFT/LoRA run** (a day of compute; the DeBERTa verifier is the right low-cost scorer for filtering at volume).
- Everything else — pipeline, verifier, retrieval interface, eval harness, report schema — is reused as-is.

### 3.7 Extension — online RL (out of POC scope, labeled next step)

Swap the offline filter for the verifier as a **live process reward** and train with GRPO/PPO: the policy explores beyond the teacher's distribution and can exceed it. This is the version that tests the "training past the prompting ceiling" thesis. It reintroduces the expensive parts: a self-hosted trainable policy + GPU/vLLM/trainer stack, a **cached offline retrieval environment** (rollouts hit search thousands of times × epochs), a high-throughput batched reward server, and — the central risk — **reward hacking** (the policy hunts verifier blind spots; multi-hop/numeric weaknesses from `limitations.md` become adversarial targets). Reward must be multi-term (`grounded + covered + calibrated − cost`) with coverage to prevent winning by dropping hard claims. This is the multi-month, productionizable-research path; the §3 POC is the cheap first step that de-risks it.

---

<!-- Add further candidate directions below as they come up. -->
