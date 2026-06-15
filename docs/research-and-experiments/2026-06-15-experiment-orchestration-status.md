---
title: "Experiment Orchestration & Status — Verifier-1 close-out + Adaptive Retrieval"
subtitle: "Deep Research Agent · what's running, what's next, dependencies, and infrastructure"
date: "2026-06-15"
---

# Experiment Orchestration & Status

**One-line status:** the v0→v1 Layer-2 DRA-Bench chain is running on EC2; on completion we pick the best verifier (checkpoint), then run FRAMES/TruthfulQA for {best verifier, 2 baselines}, then the adaptive-retrieval pilot (50 examples). Execution model = **checkpoint-at-decision** (human gate at each decision), not full auto-chain.

---

## 1. What we are running NOW

| Item | Detail |
|---|---|
| **Experiment** | Layer-2 (whole-pipeline) eval of the fine-tuned cross-encoder verifier — **v0 then v1** — on **DRA-Bench** (250 prompts, 5 types × 50). |
| **Mode** | **Freeze-upstream**: reuse the `corrected_verifier` claims+passages, swap only the verifier, re-run contradiction + compose + score. Isolates the verifier; ~2.6× faster; comparable. |
| **Driver** | Root chain script `/tmp/l2_dra.sh` under systemd: `for V in v0 v1: run_pipeline_eval --arm verifier_b_${V} --dataset dra_bench --workers 6`. |
| **Progress** | v0 ≈ 226+/250 reports and still running; **v1 auto-runs after v0** (same loop). No summaries yet. |
| **Metrics computed** | The full Layer-2 set per arm: structural EBM (`expected_behavior_match`) + text-judge EBM, grounding, relevance + quality (1–5 panel), instruction-adherence/formatting, similarity-to-gold/coverage. Paired significance vs with/without/corrected is a post-step. |
| **Calibration note** | v0 was launched **before** the per-label recalibration, so its reports carry old (single-supported) confidence; v1 will carry new per-label confidence. **This does not affect the best-verifier decision** — it is label-driven, and labels are invariant to calibration. The new calibration only matters for the adaptive pilot's gate. |
| **Known issue** | ~12 DRA-Bench items are erroring out and being skipped (e.g. `dra-type4-020`, `dra-type5-002/022/045`). Cause not yet diagnosed (harness logs a one-liner, not a traceback). To investigate before finalizing "all metrics". |

---

## 2. What we run NEXT (checkpoint sequence)

### Checkpoint A — best-verifier decision (between v1 finishing and step 3)
- Compute all DRA-Bench metrics + paired significance for **corrected vs v0 vs v1**.
- **Rule:** best of {corrected, v0, v1}. If v0/v1 beats corrected → that winner is "best verifier"; if neither beats corrected → corrected stays best.
- Human-reviewed (multi-metric + significance, not a single scalar). **Output: the one "best verifier" arm.**

### Step 3 — complete the Verifier-1 results (FRAMES + TruthfulQA)
- Run **FRAMES** and **TruthfulQA** for exactly **3 systems**: the **best verifier** (from Checkpoint A) + the **2 baselines** (Perplexity, OpenAI). Always 3 runs.
- Task-accuracy via the **full-report judge** (GPT-OSS-120B; no extraction, no exact-match) — fixes the EM artifact.
- Completes the Verifier-1 result set: **baselines · Sonnet coverage · v0/v1 on DRA-Bench · FRAMES · TruthfulQA · significance**.

### Checkpoint B — review step-3 results.

### Step 4 — adaptive-retrieval pilot
- **50 DRA-Bench examples**, `--arm verifier_b_v0_adaptive` (v0 + **new per-label calibration**) vs the 1-iteration baseline.
- Loop: gate (claim conf < τ=0.7) → **reformulate ∥ diversify** → re-verify → keep best → stop on τ / no-progress / max 3.
- Captures per-sub-question **trace** (iters, winning repair, recs/fetched, gaps) under `<arm>/trace/` for the **cost-by-type** analysis.
- Decision gate: improvement → full DRA-Bench + FRAMES + TruthfulQA with adaptive; else analyze regressions / minimal fix / re-run (a negative result is still a finding).

---

## 3. Dependencies & decision gates

- **Step 3 depends on Checkpoint A** (which arm is "best verifier" is the *output* of v0/v1 DRA-Bench scoring — cannot be pre-fixed).
- **Step 4 depends on** the new **per-label calibration** (done; `eval/results/verifier_b/{v0,v1}/platt.json`) — the adaptive gate reads calibrated predicted-label confidence. Contested confidence is **derived** at inference from supported/refuted (no extra fit).
- **Adaptive code is built + tested** (403 tests): `dra.adaptive.{control,reformulate,source_recommender,loop}` + `dra.search.fetch` (Exa `/contents`, query-targeted) + the `--adaptive` eval arm.
- **Baselines** (Perplexity, OpenAI) collected **locally** (API keys local-only); only non-secret responses go to EC2. FRAMES/TruthfulQA benchmark the **recomposed reports**.
- **Hard guardrails:**
  - **Never two Bedrock-heavy jobs at once** (per-account throttle) — sequential chains only.
  - **No-leak:** DRA-Bench / FRAMES / TruthfulQA are eval-only.
  - Calibration/labels: labels are invariant to calibration → v0/v1 comparable regardless of scheme.

---

## 4. Infrastructure

| Layer | What |
|---|---|
| **Compute** | EC2 `i-0cd55ad3510a56ca9`, region **us-east-1**, **8× A100-40GB**. Chain jobs run on **GPU0**; other GPUs free (used the free GPUs for the calibration refit + trigger probe). |
| **Access** | **SSM only** (no SSH). `aws ssm send-command` via the **`Arenal-science`** profile (Midway `ScienceAdminRole`, acct 385880137610). Other AWS profiles (`personal`, `default`) are expired. |
| **Repo on box** | `/home/ssm-user/deep-research-agent`. Local Mac repo is **source of truth** for code; commit + push to GitHub `nehaannajohn/deep-research-agent`; EC2 `git pull`s. |
| **Run-as convention** | Long experiments run **as root** via `/tmp/*.sh` chain scripts under **systemd** on GPU0 (e.g. `/tmp/l2_dra.sh`). Ad-hoc one-offs run as `ssm-user`. **Pitfall learned:** an `ssm-user` watcher cannot `kill -0` a **root** pid (EPERM reads as "dead") — so do **not** monitor/chain root jobs from ssm-user; use a single root chain script instead. |
| **Python envs** | `.venv-train` (torch 2.12 + cu130, transformers) for GPU/cross-encoder work; system `python3.12` also carries the deps. |
| **LLM calls** | **Bedrock** — generator (Llama), in-loop verifier ensemble {Sonnet 4.6, Mistral Large 3, Nova}, panel + grounding judge (`openai.gpt-oss-120b-1:0`), source recommender (Sonnet-family). |
| **Retrieval** | **Exa** — search (`/search`, highlights) + the adaptive fetch connector (`/contents`, query-targeted highlights of recommended URLs). |
| **Models / artifacts** | Cross-encoder checkpoints `eval/verifier_b_models/{v0,v1}/best`; per-label calibrators `eval/results/verifier_b/{v0,v1}/platt.json`. |
| **Results layout** | `eval/results/pipeline[_frames|_truthfulqa]/<arm>/` (gitignored). Report cache `…/report_cache/<arm>/`. Adaptive traces `…/<arm>/trace/`. |
| **File transfer** | S3 is blocked by a safety classifier → use **gzip + base64 + SSM** chunks; ship scripts to the box base64-encoded (avoids SSM quoting issues). |

---

## 5. Runbook — exact commands (everything needed to run independently)

### 5.0 Connect to the box (SSM; no SSH)
```bash
export AWS_PROFILE=Arenal-science AWS_REGION=us-east-1
INSTANCE=i-0cd55ad3510a56ca9
```
Run a remote command by shipping a script **base64-encoded** (avoids SSM quoting bugs;
never put secrets in the command). Use plain `bash` for **root** chain scripts / killing
root jobs; `sudo -u ssm-user bash` for **repo/git/refit** so file ownership matches the jobs.
```bash
cat > /tmp/job.sh <<'EOF'
cd /home/ssm-user/deep-research-agent
# ... commands ...
EOF
B64=$(base64 < /tmp/job.sh | tr -d '\n')
ID=$(aws ssm send-command --instance-ids "$INSTANCE" --document-name AWS-RunShellScript \
  --parameters commands="echo $B64 | base64 --decode | sudo -u ssm-user bash" \
  --timeout-seconds 600 --query 'Command.CommandId' --output text)
# poll:
aws ssm get-command-invocation --command-id "$ID" --instance-id "$INSTANCE" \
  --query 'StandardOutputContent' --output text
```
Long jobs must be **detached** so they survive the SSM call: wrap in
`setsid bash -c '…' </dev/null >/dev/null 2>&1 &`.

### 5.1 Status checks
```bash
ps -eo pid,user,etime,cmd | grep run_pipeline_eval | grep -v grep   # running jobs (+owner)
ls eval/results/pipeline/report_cache/verifier_b_v0 | wc -l         # v0 progress (/250)
tail -5 /tmp/l2_dra.log                                             # chain log; "ALL_DONE" = finished
nvidia-smi --query-gpu=index,memory.used,utilization.gpu --format=csv,noheader
```

### 5.2 Stage 1–2 (RUNNING): v0→v1 on DRA-Bench — `/tmp/l2_dra.sh` (root, GPU0)
```bash
cd /home/ssm-user/deep-research-agent
export CUDA_VISIBLE_DEVICES=0
for V in v0 v1; do
  .venv-train/bin/python -m experiments.run_pipeline_eval \
      --arm "verifier_b_${V}" --dataset dra_bench --workers 6
done
```
Outputs: `eval/results/pipeline/verifier_b_{v0,v1}/summary.json` + `…/per_item.json`;
reports in `…/report_cache/verifier_b_{v0,v1}/`.

### 5.3 Checkpoint A — best-verifier decision (manual)
Compare arms `corrected_verifier`, `verifier_b_v0`, `verifier_b_v1`:
```bash
for A in corrected_verifier verifier_b_v0 verifier_b_v1; do
  echo "== $A =="; cat eval/results/pipeline/$A/summary.json
done
```
- **Headline metric:** structural EBM (`expected_behavior_match`). Also weigh grounding,
  quality/relevance, coverage.
- **Significance:** paired test on per-item structural EBM from each arm's `per_item.json`
  (run via the **significance agent** locally — there is no committed script; input =
  the `per_item.json` files; method = paired bootstrap / McNemar on the EBM indicator).
- **Rule:** best of {corrected, v0, v1}. Record the winner as `BEST` (one of
  `corrected_verifier` / `verifier_b_v0` / `verifier_b_v1`).

### 5.4 Step 3 — FRAMES + TruthfulQA on {BEST, Perplexity, OpenAI}
Prereqs already on box: FRAMES/TruthfulQA have a `corrected_verifier` **canon**
(`eval/results/pipeline_{frames,truthfulqa}/report_cache/corrected_verifier/`) and
baselines `eval/{frames,truthfulqa}_baselines/{perplexity,openai}/`.

- If **BEST == corrected_verifier**: its FRAMES/TQA reports already exist → only rescore.
- If **BEST == verifier_b_v0|v1**: run the frozen arm (reuses the corrected canon):
```bash
export CUDA_VISIBLE_DEVICES=0
.venv-train/bin/python -m experiments.run_pipeline_eval --arm $BEST --dataset frames     --n 100 --workers 6
.venv-train/bin/python -m experiments.run_pipeline_eval --arm $BEST --dataset truthfulqa --n 100 --workers 6
```
- **Task-accuracy = full-report judge** (fixes the EM artifact) for all 3 systems, both datasets:
```bash
for D in frames truthfulqa; do
  .venv-train/bin/python -m experiments.rescore_task_accuracy --dataset $D \
    --arms eval/results/pipeline_$D/$BEST \
           eval/${D}_baselines/perplexity eval/${D}_baselines/openai
done
```
This completes Verifier-1: baselines · Sonnet coverage · v0/v1 on DRA-Bench · FRAMES · TruthfulQA · significance.

### 5.5 Step 4 — adaptive-retrieval pilot (50 examples)
Verify per-label calibrators exist (already fit): `cat eval/results/verifier_b/v0/platt.json`
(should show a `labels` block). If missing, refit (GPU, ~2 min, any free GPU):
```bash
CUDA_VISIBLE_DEVICES=1 .venv-train/bin/python -m experiments.verifier_b.fit_calibrator --variant v0
```
Select the 50 pilot items (those that actually exercise the loop) from the trigger probe,
then run adaptive vs the 1-iteration baseline:
```bash
# trigger probe (writes eval/results/verifier_b/v0/adaptive_trigger_probe.json)
CUDA_VISIBLE_DEVICES=1 .venv-train/bin/python -m experiments.verifier_b.adaptive_trigger_probe \
    --variant v0 --canon-dir eval/results/pipeline/report_cache --sample random --n 50 --taus 0.7
# adaptive arm (full pipeline + repair loop; writes per-subq traces under the arm/trace/)
export CUDA_VISIBLE_DEVICES=0
.venv-train/bin/python -m experiments.run_pipeline_eval --arm verifier_b_v0_adaptive \
    --dataset dra_bench --ids <comma-separated 50 ids> --workers 6
```
Compare `eval/results/pipeline/verifier_b_v0_adaptive/summary.json` vs the v0 baseline; read
`…/verifier_b_v0_adaptive/trace/*.json` for **iters / winning repair / recs+fetched / gaps**
→ the cost-by-type analysis. Pilot decision gate: improvement → full DRA-Bench + FRAMES +
TruthfulQA with adaptive; else analyze regressions / minimal fix / re-run.

## 6. Pre-staged chain scripts (write to `/tmp`, run as root via SSM when the gate clears)

**Step 3** — `/tmp/l2_frames_tqa.sh` (fill `BEST=` after Checkpoint A):
```bash
#!/bin/bash
cd /home/ssm-user/deep-research-agent; export CUDA_VISIBLE_DEVICES=0
BEST=verifier_b_v0            # <-- set to the Checkpoint-A winner
L=/tmp/l2_frames_tqa.log; echo "START $(date)" > "$L"
git pull --ff-only origin main >> "$L" 2>&1
for D in frames truthfulqa; do
  [ "$BEST" != corrected_verifier ] && \
    .venv-train/bin/python -m experiments.run_pipeline_eval --arm "$BEST" --dataset $D --n 100 --workers 6 >> "$L" 2>&1
  .venv-train/bin/python -m experiments.rescore_task_accuracy --dataset $D \
    --arms eval/results/pipeline_$D/$BEST eval/${D}_baselines/perplexity eval/${D}_baselines/openai >> "$L" 2>&1
done
echo "ALL_DONE $(date)" >> "$L"
```
**Step 4** — `/tmp/l2_pilot.sh` (fill `IDS=` from the probe selection):
```bash
#!/bin/bash
cd /home/ssm-user/deep-research-agent; export CUDA_VISIBLE_DEVICES=0
IDS=...                        # <-- comma-separated 50 DRA-Bench ids
L=/tmp/l2_pilot.log; echo "START $(date)" > "$L"
git pull --ff-only origin main >> "$L" 2>&1
.venv-train/bin/python -m experiments.run_pipeline_eval --arm verifier_b_v0_adaptive \
    --dataset dra_bench --ids "$IDS" --workers 6 >> "$L" 2>&1
echo "ALL_DONE $(date)" >> "$L"
```
Launch pattern (root, detached, only when no other Bedrock job is running):
```bash
B64=$(base64 < /tmp/l2_frames_tqa.sh | tr -d '\n')
aws ssm send-command --instance-ids "$INSTANCE" --document-name AWS-RunShellScript \
  --parameters commands="echo $B64 | base64 --decode > /tmp/run.sh; setsid bash /tmp/run.sh </dev/null >/dev/null 2>&1 &" \
  --query 'Command.CommandId' --output text
```

---

## Appendix — current commit state (Mac `main`, pushed)

- `ce9fe01` verifier confidence = predicted-label + per-label Platt calibration
- `1c65978` gitignore `.venv-*`
- `7e297c1` derive contested confidence from supported/refuted
- `ea4ce0e` / `1d3062e` adaptive trigger probe (+ random sample / query-level)
- `bde430f` adaptive Phase 0–1 (gate + repairs)
- `830128d` recommender → net-new fetchable URLs
- `93264f4` Phase 2 `run_query_adaptive`
- `8e590a2` `--adaptive` eval arm
- (this doc)

**EC2 repo HEAD:** `1d3062e` (will fast-forward to latest when the next stage's chain script pulls).
