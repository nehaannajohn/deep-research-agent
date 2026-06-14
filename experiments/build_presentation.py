"""Build the Deep Research Agent presentation (.pptx) — clean professional style.

Run: .venv/bin/python experiments/build_presentation.py
Output: ~/Desktop/DeepResearchAgent_Presentation.pptx
"""
from __future__ import annotations
import os
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

# ---- palette (clean professional) ----
NAVY   = RGBColor(0x1B, 0x2A, 0x4A)
ACCENT = RGBColor(0x2E, 0x86, 0xAB)
ACC_DK = RGBColor(0x21, 0x60, 0x7A)
LIGHT  = RGBColor(0xEE, 0xF2, 0xF6)
ROW_ALT= RGBColor(0xF6, 0xF8, 0xFA)
INK    = RGBColor(0x22, 0x28, 0x33)
GRAY   = RGBColor(0x5C, 0x66, 0x72)
WHITE  = RGBColor(0xFF, 0xFF, 0xFF)
GREEN  = RGBColor(0x1E, 0x7D, 0x4F)
AMBER  = RGBColor(0xB5, 0x6A, 0x00)

EMU_W, EMU_H = Inches(13.333), Inches(7.5)
prs = Presentation()
prs.slide_width, prs.slide_height = EMU_W, EMU_H
BLANK = prs.slide_layouts[6]
_page = [0]


def _box(slide, l, t, w, h, fill=None, line=None, line_w=None):
    shp = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, l, t, w, h)
    shp.shadow.inherit = False
    if fill is None:
        shp.fill.background()
    else:
        shp.fill.solid(); shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line; shp.line.width = line_w or Pt(1)
    return shp


def _text(slide, l, t, w, h, runs, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, wrap=True):
    """runs: list of paragraphs; each = list of (text, size, color, bold, level)."""
    tb = slide.shapes.add_textbox(l, t, w, h); tf = tb.text_frame
    tf.word_wrap = wrap; tf.vertical_anchor = anchor
    for i, para in enumerate(runs):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        if isinstance(para, tuple):
            para = [para]
        for j, (txt, size, color, bold, level) in enumerate(para):
            r = p.add_run(); r.text = txt
            r.font.size = Pt(size); r.font.color.rgb = color; r.font.bold = bold
            r.font.name = "Calibri"
            p.level = level
        p.space_after = Pt(6)
    return tb


def header(slide, kicker, title):
    _box(slide, 0, 0, EMU_W, Inches(1.15), fill=WHITE)
    _box(slide, 0, Inches(1.15), EMU_W, Pt(3), fill=ACCENT)
    _box(slide, Inches(0.0), Inches(0.18), Inches(0.16), Inches(0.8), fill=ACCENT)
    _text(slide, Inches(0.45), Inches(0.16), Inches(12.4), Inches(0.34),
          [(kicker.upper(), 12, ACCENT, True, 0)])
    _text(slide, Inches(0.45), Inches(0.44), Inches(12.4), Inches(0.66),
          [(title, 26, NAVY, True, 0)])


def footer(slide):
    _page[0] += 1
    _text(slide, Inches(0.45), Inches(7.06), Inches(8), Inches(0.34),
          [("Deep Research Agent  ·  Neha Anna John", 9, GRAY, False, 0)])
    _text(slide, Inches(11.8), Inches(7.06), Inches(1.1), Inches(0.34),
          [(str(_page[0]), 9, GRAY, False, 0)], align=PP_ALIGN.RIGHT)


def content(kicker, title):
    s = prs.slides.add_slide(BLANK)
    _box(s, 0, 0, EMU_W, EMU_H, fill=WHITE)
    header(s, kicker, title); footer(s)
    return s


def bullets(slide, items, left=Inches(0.55), top=Inches(1.45),
            width=Inches(12.2), height=Inches(5.3), size=15, gap=7):
    """items: list of (text, level). level 0 = •, level 1 = – sub."""
    tb = slide.shapes.add_textbox(left, top, width, height); tf = tb.text_frame
    tf.word_wrap = True
    for i, (txt, lvl) in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.level = lvl
        bullet = "•  " if lvl == 0 else "–  "
        r = p.add_run(); r.text = bullet + txt
        r.font.size = Pt(size if lvl == 0 else size - 2)
        r.font.color.rgb = INK if lvl == 0 else GRAY
        r.font.bold = False; r.font.name = "Calibri"
        p.space_after = Pt(gap)
    return tb


def table(slide, headers, rows, left=Inches(0.55), top=Inches(1.55),
          width=Inches(12.2), col_w=None, fsize=12, hsize=12, first_bold=False,
          height=Inches(0.4)):
    nr, nc = len(rows) + 1, len(headers)
    gt = slide.shapes.add_table(nr, nc, left, top, width, height).table
    if col_w:
        total = sum(col_w)
        for i, w in enumerate(col_w):
            gt.columns[i].width = int(width * w / total)
    for j, h in enumerate(headers):
        c = gt.cell(0, j); c.text = ""
        p = c.text_frame.paragraphs[0]; r = p.add_run(); r.text = h
        r.font.bold = True; r.font.size = Pt(hsize); r.font.color.rgb = WHITE; r.font.name = "Calibri"
        c.fill.solid(); c.fill.fore_color.rgb = NAVY
        c.vertical_anchor = MSO_ANCHOR.MIDDLE
        c.margin_top = Pt(3); c.margin_bottom = Pt(3)
    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            c = gt.cell(i + 1, j); c.text = ""
            p = c.text_frame.paragraphs[0]
            p.word_wrap = True
            r = p.add_run(); r.text = str(val)
            r.font.size = Pt(fsize); r.font.color.rgb = INK; r.font.name = "Calibri"
            r.font.bold = bool(first_bold and j == 0)
            c.fill.solid(); c.fill.fore_color.rgb = ROW_ALT if i % 2 else WHITE
            c.vertical_anchor = MSO_ANCHOR.MIDDLE
            c.margin_top = Pt(2); c.margin_bottom = Pt(2)
            c.margin_left = Pt(6)
    return gt


def pipeline_row(slide, stages, top=Inches(2.0), models=None, h=Inches(1.0)):
    n = len(stages)
    gap = Inches(0.18)
    total_w = Inches(12.4)
    bw = (total_w - gap * (n - 1)) / n
    left0 = Inches(0.45)
    for i, st in enumerate(stages):
        l = left0 + i * (bw + gap)
        b = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, l, top, bw, h)
        b.shadow.inherit = False
        b.fill.solid(); b.fill.fore_color.rgb = ACCENT if i % 2 == 0 else ACC_DK
        b.line.fill.background()
        tf = b.text_frame; tf.word_wrap = True; tf.vertical_anchor = MSO_ANCHOR.MIDDLE
        tf.margin_left = Pt(3); tf.margin_right = Pt(3)
        p = tf.paragraphs[0]; p.alignment = PP_ALIGN.CENTER
        r = p.add_run(); r.text = st; r.font.size = Pt(10.5); r.font.bold = True
        r.font.color.rgb = WHITE; r.font.name = "Calibri"
        if i < n - 1:
            a = slide.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, l + bw - Inches(0.02), top + h/2 - Inches(0.08), gap + Inches(0.04), Inches(0.16))
            a.shadow.inherit = False
            a.fill.solid(); a.fill.fore_color.rgb = GRAY; a.line.fill.background()
        if models:
            _text(slide, l, top + h + Inches(0.06), bw, Inches(0.9),
                  [(models[i], 9, GRAY, False, 0)], align=PP_ALIGN.CENTER)


# =========================================================== SLIDES

# 1 — Title
s = prs.slides.add_slide(BLANK)
_box(s, 0, 0, EMU_W, EMU_H, fill=NAVY)
_box(s, 0, Inches(4.5), EMU_W, Pt(4), fill=ACCENT)
_box(s, Inches(0.9), Inches(2.55), Inches(0.18), Inches(1.6), fill=ACCENT)
_text(s, Inches(1.25), Inches(2.5), Inches(11), Inches(1.5),
      [("Deep Research Agent", 48, WHITE, True, 0)])
_text(s, Inches(1.28), Inches(3.75), Inches(11), Inches(0.7),
      [("A transparent, reliable research pipeline — verification as the spine", 20, RGBColor(0xBF,0xD4,0xE0), False, 0)])
_text(s, Inches(1.28), Inches(4.75), Inches(11), Inches(0.6),
      [("Neha Anna John", 20, WHITE, True, 0)])
_text(s, Inches(1.28), Inches(5.25), Inches(11), Inches(0.5),
      [("Reinforce Labs — Research & Post-training take-home", 14, RGBColor(0x9F,0xB4,0xC4), False, 0)])

# 2 — Agenda
s = content("Overview", "Agenda")
bullets(s, [
    ("Challenges of deep-research agents in today's ecosystem", 0),
    ("The objective: a transparent, reliable research agent", 0),
    ("The larger architecture and its safeguards", 0),
    ("The MVP pipeline — and what makes it transparent & reliable", 0),
    ("How fast design choices were made (small-scale experiments)", 0),
    ("The pipeline, annotated with the models behind each stage", 0),
    ("Verifier deep-dive — with / without / corrected / fine-tuned v0·v1", 0),
    ("Known limitations", 0),
    ("Future exploration — including the verifier as a process reward model", 0),
], size=17, gap=9)

# 3 — Ecosystem challenges
s = content("1 · Ecosystem challenges", "The hard problem is verification, not generation")
bullets(s, [
    ("Most deep-research systems produce plausible output but lack rigorous per-claim verification", 0),
    ("Recursive & plan-execute agents (GPT-Researcher, STORM, LangChain Open DR) have no per-claim verification step", 0),
    ("Aggregating 20+ sources is not verification — source count ≠ grounding", 0),
    ("Citation quality ≠ factual accuracy: >94% valid links, but only 39–77% factual; accuracy drops ~42% as tool calls scale 2→150", 0),
    ("Self-evaluation yields zero calibration without external labels (\"the verification tax\")", 0),
    ("Faithfulness ≠ correctness — outcome-correct agents can still reason unfaithfully; endpoint checks miss it", 0),
    ("Homogeneous judge panels fail: 9 correlated judges ≈ only 2 effective votes", 0),
    ("No deployed system unifies verification + calibrated confidence + adaptive retrieval in one loop", 0),
], size=14.5, gap=8)

# 4 — Landscape + the gap
s = content("1 · Ecosystem challenges", "The landscape — and the gap we target")
table(s, ["Pattern", "Examples", "Verification / confidence"], [
    ["Recursive tree", "dzhng/deep-research, GPT-Researcher Deep", "none · no confidence"],
    ["Plan-and-execute (most deployed)", "GPT-Researcher, LangChain Open DR, AWS Strands", "no per-claim confidence"],
    ["Multi-perspective", "Stanford STORM, Co-STORM", "no explicit fact-checking"],
    ["RL-trained search", "Search-R1, Alibaba DeepResearch, WebThinker", "SOTA but 8×A100+, inaccessible"],
    ["Commercial", "Perplexity Sonar, OpenAI", "black-box; grounding not exposed"],
], col_w=[2.2, 4.2, 3.2], fsize=12, top=Inches(1.55), height=Inches(3.0))
_text(s, Inches(0.55), Inches(5.05), Inches(12.2), Inches(1.6), [
    [("The deployment blocker for agents is measurable trust.  ", 15, NAVY, True, 0)],
    [("We unify verification + calibrated per-claim confidence + adaptive retrieval in one loop — to distinguish ", 14, INK, False, 0),
     ("plausible from correct", 14, ACCENT, True, 0),
     (" (the field's open problem; today only academic, none deployed).", 14, INK, False, 0)],
])

# 5 — MVP objective
s = content("2 · Objective", "A transparent, reliable deep research agent")
bullets(s, [
    ("Given a query → a structured, evidence-backed report", 0),
    ("Reliable — every claim is verified against its evidence; weakly-grounded claims trigger adaptive retrieval", 0),
    ("Transparent — calibrated confidence per claim; explicit where evidence is thin, never papering over uncertainty", 0),
    ("Spine = evaluation — the blocker to deploying agents is not capability, it is measurable trust", 0),
    ("Quality made measurable at train-time (learned verifier), inference-time (calibrated confidence + adaptive retrieval), and offline (eval framework)", 0),
    ("Build vs. buy — buy retrieval (commodity); build deep: verification, adaptive retrieval, report generation, evaluation", 0),
], size=15.5, gap=11)

# 6 — Larger architecture
s = content("3 · Larger architecture", "Defense-in-depth: 9 layers, outer → inner")
bullets(s, [
    ("Guardrails (moderation + PII) → Clarification (brief + constraints) → Planner (sub-questions) → Router (academic / web / user tool)", 0),
    ("→ Evidence (verbatim passages) → Synthesis (atomic claims + citations) → Verification + calibrated confidence → Report assembly", 0),
    ("Cross-cutting: observability + cost budget; egress guardrails before any output", 0),
    ("Verification loops back to the Router on low-confidence / insufficient — diagnosis → treatment in one loop", 0),
    ("Source credibility — every source carries a reliability note; contested is a first-class verdict when sources genuinely disagree", 0),
    ("Honesty on failure — at unresolved max-iters, ship the claim flagged insufficient with a disclaimer, never fabricate", 0),
], size=15, gap=10)

# 7 — Safeguards / invariants
s = content("3 · Safeguards", "Design invariants (the guardrails)")
bullets(s, [
    ("Evidence is verbatim, never summarized — verifying against an LLM summary would be circular", 0),
    ("Model independence — distinct model families at every evaluative boundary so biases don't correlate; enforced by config.assert_independence()", 0),
    ("Generator proposes, verifier confirms — candidate citation ids are untrusted; an independent verifier confirms entailment(passage ⊨ claim)", 0),
    ("Confidence is recalibrated before being surfaced (temperature scaling / isotonic); report uses the recalibrated value, reports ECE before vs after", 0),
    ("Surface all terminal claims — supported (confident), contested (both sides flagged), insufficient (gap + disclaimer); never silently drop", 0),
    ("Verification + adaptive retrieval are one loop; coverage tracked so the system can't win by deleting hard claims", 0),
], size=14.5, gap=9)

# 8 — MVP pipeline
s = content("4 · MVP pipeline", "Query → evidence-backed report")
pipeline_row(s, ["Query", "Decompose", "Retrieve (Exa)", "Extract claims", "Verify", "Contradiction detection", "Compose report", "Evaluate"],
             top=Inches(1.7), h=Inches(1.05))
_text(s, Inches(0.55), Inches(3.2), Inches(12.2), Inches(0.4),
      [("Adaptive loop is verdict-routed: supported≥τ → accept · insufficient → reformulate & re-search · refuted → revise / contest · weak source → switch tool   (terminate on τ | max_iters≈3 | no-progress | budget)", 12.5, GRAY, False, 0)])
table(s, ["Transparency comes from", "Reliability comes from"], [
    ["Offline evaluation harness — decomposes any report into claims, runs verifier + blind judge panel",
     "Verifier labels each claim's grounding via entailment {supported / refuted / insufficient / contested}"],
    ["Per-claim calibrated confidence surfaced in the report (claim ledger separates claims from evidence)",
     "Contradiction detection — claim↔citation (grounding), claim↔claim (consistency), citation↔citation (contested)"],
], col_w=[1,1], fsize=12.5, top=Inches(3.8), height=Inches(2.6))

# 9 — Quick choice: Exa vs Tavily
s = content("5 · Quick choices", "Retrieval engine — Exa vs Tavily (12-query bake-off)")
table(s, ["Engine", "recall@k", "relevance", "latency", "panel mean"], [
    ["Exa  ✓", "0.333", "0.919", "1.4 s", "0.892"],
    ["Tavily", "0.250", "0.764", "3.5 s", "0.768"],
    ["Semantic Scholar", "0.000", "0.000", "— (429s)", "—"],
], col_w=[2.6, 1.6, 1.6, 1.6, 1.8], fsize=13, top=Inches(1.6), height=Inches(1.9))
bullets(s, [
    ("Exa wins on every axis; 4-judge cross-check (72 passages) ranks Exa > Tavily by a consistent ~0.12 margin", 0),
    ("Use Exa highlights — verbatim query-targeted excerpts (not full text), preserving the extractive-citation invariant", 0),
    ("Settled hyperparameters: k = 5 per sub-question · maxChars = 2,000 · decomposition ON  (Tavily retained as fallback)", 0),
], left=Inches(0.55), top=Inches(3.8), size=14.5, gap=10)

# 10 — Quick choice: decomposition
s = content("5 · Quick choices", "Query decomposition vs none")
bullets(s, [
    ("Decision: KEEP decomposition (flexible 1…N sub-questions; split only for distinct evidence)", 0),
    ("Across 4 cases at a fixed 2k budget, decomposition surfaced 3–4× more unique sources with low overlap:", 0),
    ("8 → 27–36 sources per query (e.g. tc4: 8 → 36, Jaccard 0.02)", 1),
    ("extra sources are relevant — including canonical primaries the broad query misses (e.g. the original CoT paper)", 1),
    ("No over-splitting — atomic probes (\"max context window of Llama 4 Maverick\") return exactly 1 sub-question, unchanged", 0),
], size=15, gap=10)

# 11 — Quick choice: claim extraction
s = content("5 · Quick choices", "Claim extraction — generator model")
table(s, ["Model", "Grounding (0–2)", "Atomicity (0/1)", "Note"], [
    ["Llama 4 Maverick (17B)  ✓", "1.24", "0.80", "smallest model wins the north-star metric"],
    ["Haiku 4.5", "0.97", "0.74", "dropped"],
    ["Mistral Large 3 (675B)", "0.94", "0.73", "over-reaches — 635 claims vs Llama's 147 (4×)"],
], col_w=[2.8, 1.8, 1.7, 4.0], fsize=12.5, top=Inches(1.6), height=Inches(1.9))
bullets(s, [
    ("All 3 judges rank Llama > Haiku > Mistral on grounding (unanimous, n=8)", 0),
    ("Mistral over-reaches from parametric memory (confident specifics, citation stapled on) — structural, not prompt-fixable", 0),
    ("Outcome: Mistral re-roled to the in-loop verifier ensemble; generator max_tokens 1024 → 8192", 0),
], top=Inches(3.8), size=14.5, gap=10)

# 12 — Quick choice: structural formatting
s = content("5 · Quick choices", "Structural formatting as a separate component")
bullets(s, [
    ("Split the query into core-research-query + constraints {wants_visual, format, focus}", 0),
    ("Route formatting / modality instructions to report composition — NOT to retrieval", 0),
    ("Why: keeps a \"include a diagram\" instruction from changing the evidence retrieved", 1),
    ("validated: retrieval is identical across plain vs format-augmented arms (cache-confirmed)", 1),
    ("Hybrid composition: LLM writes narrative + artifacts (Mermaid diagram / table on demand); a deterministic layer renders the claim table, metadata, disclaimers, sources — never LLM-paraphrased", 0),
    ("Constrain-by-construction honesty: every factual sentence must cite an existing ledger claim id [cN]; a guard flags any [cN] not in the ledger", 0),
], size=14.5, gap=9)

# 13 — Pipeline annotated with models
s = content("6 · Models", "The pipeline, annotated with models")
pipeline_row(s, ["Query", "Decompose", "Retrieve", "Extract claims", "Verify", "Contradiction", "Compose"],
             top=Inches(1.7), h=Inches(0.95),
             models=["—", "Llama 4 Maverick", "Exa", "Llama 4 Maverick", "Ensemble: Sonnet · Mistral L3 · Nova", "in-loop verifier", "Llama 4 Maverick"])
bullets(s, [
    ("Generator (decompose, claim extraction, report) = Llama 4 Maverick", 0),
    ("In-loop verifier = 3-model ensemble {Sonnet 4.6, Mistral Large 3, Amazon Nova} — majority vote + agreement confidence, 4-way incl. contested", 0),
    ("Model independence enforced: generator ≠ verifier ≠ judge panel ≠ baseline (config.assert_independence())", 0),
    ("Verifier B (the A-vs-B alternative) = a fine-tuned DeBERTa-v3 cross-encoder — see next section", 0),
], top=Inches(4.1), size=13.5, gap=8)

# 14 — Verifier: what it does
s = content("7 · Verifier", "What does the verifier do?")
bullets(s, [
    ("Takes an atomic claim + its cited passages → emits a grounding verdict {supported · refuted · insufficient · contested} + a measured confidence", 0),
    ("Checks entailment (passage ⊨ claim) — grounding against the evidence, NOT world knowledge", 0),
    ("Drives adaptive retrieval (verdict-routed) and surfaces per-claim confidence (transparency) — it is the reliability spine", 0),
    ("Without it there are no grounding / contested / insufficient labels — no defensible reliability claim", 0),
    ("Two evaluation layers: Layer-1 (verifier in isolation) and Layer-2 (the verifier inside the whole pipeline)", 0),
], size=15.5, gap=12)

# 15 — Verifier types comparison
s = content("7 · Verifier", "The verifier variants compared")
table(s, ["Variant", "Training data / prompting", "What it achieves"], [
    ["with verifier (A)", "LLM-judge ensemble {Sonnet, Mistral, Nova}, zero-shot; contradiction layer ON (original prompt)", "holistic 4-way verdict; strong honesty signal — but over-flags settled claims as contested"],
    ["corrected verifier", "same ensemble + structured-reasoning contradiction prompt", "keeps the honesty, recovers the quality lost to over-flagging"],
    ["without verifier", "none — claims surfaced unverified", "baseline; no grounding / contested / insufficient labels"],
    ["v0 (Verifier B)", "fine-tuned DeBERTa-v3 cross-encoder on FEVER+SciFact + Platt", "competent, calibratable, ~130× faster & cheaper"],
    ["v1 (Verifier B)", "v0 data + our-distribution synthetic hard-negatives + evidence-ablated curriculum", "more conservative (abstains on thin evidence); marginally worse on clean benchmark"],
], col_w=[1.7, 4.6, 4.3], fsize=11.5, top=Inches(1.55), height=Inches(4.2))

# 16 — Benchmarks
s = content("7 · Verifier", "Benchmarks")
bullets(s, [
    ("Layer-1 — verifier in isolation, against labelled component benchmarks:", 0),
    ("FEVER (n=1000) + SciFact (n=300), 3-way; plus a constructed contested set (75 / dataset)", 1),
    ("metrics: macro-F1, ECE (before/after Platt), AUROC, Brier, latency", 1),
    ("Layer-2 — the verifier inside the whole pipeline, scoring the finished report:", 0),
    ("DRA-Bench — 250 epistemic-behavior prompts (5 types: answer-confident / contested / insufficient …)", 1),
    ("FRAMES (multi-hop QA, n=100) + TruthfulQA (adversarial misconceptions, n=100)", 1),
    ("metrics: grounding, expected-behavior-match (structural + text), relevance, quality, task-accuracy", 1),
    ("Significance throughout: paired-t (continuous), McNemar (binary), Holm correction", 0),
], size=14, gap=7)

# 17 — Layer-1 results
s = content("7 · Verifier — results", "Layer-1: a small fine-tuned verifier matches the ensemble, ~130× faster")
table(s, ["Verifier", "macro-F1", "ECE (post-Platt)", "AUROC", "latency p50", "speedup"], [
    ["Ensemble A (3 LLM judges)", "0.815", "0.031", "0.936", "2,485 ms", "1×"],
    ["v0 — calibrated  ✓", "0.839", "0.039", "0.966", "19 ms", "130×"],
    ["v1 — calibrated", "0.834", "0.059", "0.962", "19 ms", "132×"],
], col_w=[3.0, 1.6, 2.0, 1.5, 1.7, 1.4], fsize=13, top=Inches(1.7), height=Inches(1.9), first_bold=True)
bullets(s, [
    ("Combined FEVER+SciFact 3-way, n=1300. Best B = v0: competency parity with the ensemble, well-calibrated, far stronger AUROC", 0),
    ("The decisive axis is latency / cost — one local 184M forward pass replaces three Bedrock LLM calls per claim", 0),
    ("v1's our-distribution curriculum didn't help on the clean benchmark — it is the more conservative model", 0),
], top=Inches(3.9), size=14, gap=9)

# 18 — Layer-2 results
s = content("7 · Verifier — results", "Layer-2: the over-flagging fix — honesty kept, quality recovered")
table(s, ["Metric (DRA-Bench)", "with", "without", "corrected"], [
    ["EBM — structural (honesty)", "0.807", "0.595", "0.794"],
    ["EBM — text (reader-facing)", "0.786", "0.810", "0.794"],
    ["quality (1–5)", "3.895", "4.118", "4.105"],
    ["grounding rate", "0.956", "0.959", "0.953"],
], col_w=[3.4, 1.4, 1.4, 1.6], fsize=12.5, top=Inches(1.65), height=Inches(2.4), first_bold=True)
bullets(s, [
    ("corrected = with's structural-EBM honesty (tied; ≫ without) at without's quality (+0.181 vs with, Holm-significant)", 0),
    ("text-EBM is statistically flat across all three arms — the structural honesty gain doesn't fully reach the reader (over-flagging)", 0),
    ("grounding is flat with vs without the verifier (all 3 benchmarks) — grounding is gated on retrieval, not verification", 0),
], top=Inches(4.3), size=13.5, gap=8)

# 19 — v0/v1 Layer-2 (pending)
s = content("7 · Verifier — results", "v0 / v1 in the pipeline (Layer-2) — in progress")
_box(s, Inches(0.55), Inches(1.7), Inches(12.2), Inches(1.2), fill=LIGHT, line=AMBER, line_w=Pt(1.5))
_text(s, Inches(0.8), Inches(1.95), Inches(11.7), Inches(0.8), [
    [("⏳  Running now — ", 15, AMBER, True, 0),
     ("the calibrated v0 and v1 cross-encoders are being dropped into the full pipeline across DRA-Bench, FRAMES and TruthfulQA.", 15, INK, False, 0)]])
bullets(s, [
    ("The question: does Layer-1's winner (v0) also win at Layer-2 under real multi-passage retrieval?", 0),
    ("And does v1's conservatism — penalized by FEVER gold, which can encode world knowledge beyond the shown evidence — become an asset on messy retrieved evidence?", 0),
    ("Prerequisite shipped: the verify() multi-passage over-flip fix (per-passage argmax voting)", 0),
    ("Results backfill this slide on completion", 1),
], top=Inches(3.3), size=14.5, gap=10)

# 20 — Key learnings
s = content("7 · Verifier", "Key learnings")
bullets(s, [
    ("The verifier is a must-have — it is the only source of grounding / contested / insufficient labels", 0),
    ("The contradiction layer is necessary but retrieval-bound; over-flagging is fixable at the prompt (corrected), not removable", 0),
    ("The structural honesty gain doesn't fully reach the reader (text-EBM flat) — the corrected prompt restores quality", 0),
    ("Grounding is gated on retrieval, not verification — flat across all arms and benchmarks. The ceiling is retrieval.", 0),
    ("A small fine-tuned verifier (v0) matches the ensemble, calibrates well, and is ~130× faster → a viable cheaper drop-in", 0),
    ("Evidence-faithful abstention (v1) is penalized by single-evidence benchmarks but may be an asset under real retrieval", 0),
], size=14.5, gap=10)

# 21 — Limitations 1
s = content("8 · Limitations", "Known limitations (1 / 2)")
bullets(s, [
    ("Per-component choices rest on small-scale evals — not statistically powered; conclusions could shift on larger samples", 0),
    ("The verifier checks grounding, not source credibility — a claim can be faithfully grounded in a low-quality source", 0),
    ("Tested only on English, text-only queries — no multilingual or multimodal coverage", 0),
    ("Static retrieval defaults (k=5, maxChars=2k); no feedback-driven per-query adaptivity in the MVP", 0),
    ("Coverage plateaus ~80–85% and is flat beyond k=5 — a single-backend (Exa) breadth limit, not a depth problem", 0),
], size=15, gap=11)

# 22 — Limitations 2
s = content("8 · Limitations", "Known limitations (2 / 2)")
bullets(s, [
    ("Layer-1 benchmarks present a single curated evidence per claim — easier & cleaner than the real multi-passage operating mode; gold can encode world knowledge beyond the shown evidence", 0),
    ("Format-augmented queries aren't byte-identical in retrieval — the LLM core-query extraction drifts slightly across phrasings", 0),
    ("DRA-Bench gold (Sonnet 4.6) and the judge panel (incl. Opus) share the Anthropic family — a mild self-preference risk on the relevance/quality axes (grounding is judged by a non-Anthropic model)", 0),
    ("The headline ceiling — verification + contradiction are retrieval-bound; their quality ceiling sits upstream at retrieval quality / diversity / source-selection, not at the components themselves", 0),
], size=14.5, gap=11)

# 23 — Future exploration
s = content("9 · Future exploration", "Where this goes next")
bullets(s, [
    ("Adaptive / multi-backend retrieval + source-credibility weighting + route-by-query-type — the lever that actually moves the ceiling", 0),
    ("Deterministic core-query extraction; multilingual & multimodal inputs", 0),
    ("Verifier as a Process Reward Model (PRM) for a learned adaptive-retrieval controller:", 0),
    ("the verifier wears three hats — judge, calibrated confidence, and dense step reward (Δp_supported) to a GRPO-trained ActionSelector", 1),
    ("gated before any RL run: a monotonicity ladder (≥90% per distribution) + an anti-gaming insensitivity check; gold labels anchor terminal reward", 1),
    ("caveat: a PRM/policy can't exceed the retrieval ceiling — grounding stays flat across arms, bounding its value", 1),
    ("DSPy prompt optimization · RL-trained research policy via verifier-supervised distillation · LangGraph orchestration · Fable benchmarking", 0),
], size=14, gap=8)

# 24 — Closing
s = prs.slides.add_slide(BLANK)
_box(s, 0, 0, EMU_W, EMU_H, fill=NAVY)
_box(s, Inches(0.9), Inches(2.3), Inches(0.18), Inches(2.4), fill=ACCENT)
_text(s, Inches(1.25), Inches(2.2), Inches(11), Inches(1.0),
      [("Measurable trust is the deployment blocker", 34, WHITE, True, 0)])
_text(s, Inches(1.28), Inches(3.4), Inches(11.2), Inches(2.6), [
    [("Verification + calibrated per-claim confidence + adaptive retrieval, in one loop —", 17, RGBColor(0xCF,0xDF,0xEA), False, 0)],
    [("the means to distinguish plausible from correct.", 17, RGBColor(0xCF,0xDF,0xEA), False, 0)],
    [(" ", 8, WHITE, False, 0)],
    [("The verifier is the spine. A 184M fine-tune can carry it ~130× cheaper.", 17, WHITE, True, 0)],
    [("And the ceiling we found is retrieval — which is exactly where we go next.", 17, WHITE, True, 0)],
])
_text(s, Inches(1.28), Inches(6.4), Inches(11), Inches(0.5),
      [("Thank you  ·  Neha Anna John", 15, RGBColor(0x9F,0xB4,0xC4), False, 0)])

out = os.path.expanduser("~/Desktop/DeepResearchAgent_Presentation.pptx")
prs.save(out)
print(f"saved {len(prs.slides.__iter__.__self__._sldIdLst)} slides -> {out}")
