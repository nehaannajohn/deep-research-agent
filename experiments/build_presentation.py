"""Build the Deep Research Agent presentation (.pptx) — clean professional style.

Run: .venv/bin/python experiments/build_presentation.py
Output: ~/Desktop/DeepResearchAgent_Presentation.pptx

Writing style: plain language for an audience new to the project. State
conclusions, not raw statistics; define terms on first use; one idea per line.
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
      [("A research agent you can trust — every claim checked against its sources", 20, RGBColor(0xBF,0xD4,0xE0), False, 0)])
_text(s, Inches(1.28), Inches(4.75), Inches(11), Inches(0.6),
      [("Neha Anna John", 20, WHITE, True, 0)])
_text(s, Inches(1.28), Inches(5.25), Inches(11), Inches(0.5),
      [("Reinforce Labs — Research & Post-training take-home", 14, RGBColor(0x9F,0xB4,0xC4), False, 0)])

# 2 — Agenda
s = content("Overview", "Agenda")
bullets(s, [
    ("Why today's deep-research agents fall short", 0),
    ("Our goal: a transparent, reliable research agent", 0),
    ("The full system design and its safeguards", 0),
    ("The working pipeline — and what makes it trustworthy", 0),
    ("How we made fast design choices with small experiments", 0),
    ("The pipeline, with the model behind each step", 0),
    ("The verifier: on, off, improved, and replaced by a small trained model", 0),
    ("Known limitations", 0),
    ("Where this goes next", 0),
], size=17, gap=9)

# 3 — Ecosystem challenges
s = content("1 · The problem", "Today's research agents write well — but don't check facts")
bullets(s, [
    ("Most deep-research systems produce fluent answers but never verify whether each claim is actually true", 0),
    ("Popular agents (GPT-Researcher, STORM, LangChain) have no step that checks individual claims against their sources", 0),
    ("Gathering 20+ sources is not the same as verifying — more sources does not mean better grounding", 0),
    ("Even when links are valid, the facts often are not: studies report 39–77% factual accuracy, and it drops sharply as the agent takes more search steps", 0),
    ("A model grading its own work tells you nothing reliable without an independent check", 0),
    ("Getting the final answer right does not mean the reasoning was sound — checking only the endpoint misses this", 0),
    ("Panels of similar judge-models mostly agree with each other, not with the truth — false confidence", 0),
    ("No deployed system combines claim-checking, trustworthy confidence, and adaptive search in one loop", 0),
], size=14.5, gap=8)

# 4 — Landscape + the gap
s = content("1 · The problem", "The landscape — and the gap we target")
table(s, ["Approach", "Examples", "Verification / confidence"], [
    ["Recursive search", "dzhng/deep-research, GPT-Researcher Deep", "none · no confidence"],
    ["Plan-and-execute (most common)", "GPT-Researcher, LangChain Open DR, AWS Strands", "no per-claim confidence"],
    ["Multi-perspective", "Stanford STORM, Co-STORM", "no explicit fact-checking"],
    ["Self-trained (RL) search", "Search-R1, Alibaba DeepResearch, WebThinker", "strong, but need huge GPU clusters — out of reach"],
    ["Commercial", "Perplexity, OpenAI", "black box — grounding not shown"],
], col_w=[2.4, 4.2, 3.2], fsize=12, top=Inches(1.55), height=Inches(3.0))
_text(s, Inches(0.55), Inches(5.05), Inches(12.2), Inches(1.6), [
    [("What blocks deployment isn't capability — it's trust you can measure.", 15, NAVY, True, 0)],
    [("We combine claim-checking, trustworthy per-claim confidence, and adaptive search in one loop — to tell ", 14, INK, False, 0),
     ("plausible apart from correct", 14, ACCENT, True, 0),
     (".  No system does all three today.", 14, INK, False, 0)],
])

# 5 — Objective
s = content("2 · Goal", "A transparent, reliable deep research agent")
bullets(s, [
    ("Input a question → output a structured report where every claim is backed by a source", 0),
    ("Reliable — each claim is checked against its evidence; weakly-supported claims trigger another round of searching", 0),
    ("Transparent — every claim carries a confidence score, and the report says plainly when the evidence is thin", 0),
    ("The hard part is not writing — it is earning trust. So evaluation is the backbone of the whole project.", 0),
    ("Build vs. buy — we buy search (a commodity) and build the hard parts: verification, the search loop, report writing, and evaluation", 0),
], size=15.5, gap=12)

# 6 — Larger architecture
s = content("3 · Full design", "Defense in depth — nine layers, outer to inner")
bullets(s, [
    ("Outer guardrails (content moderation, strip personal data) → clarify the request → plan sub-questions → route each to a search tool", 0),
    ("Core: fetch exact source passages → pull out individual factual claims with citations → verify each claim and score confidence → assemble the report", 0),
    ("Throughout: track cost and behaviour, and run a final safety check before anything is shown", 0),
    ("When confidence is low, verification sends the system back to search for better evidence — this is the loop", 0),
    ("Sources carry a credibility note; \"contested\" is a real verdict when good sources genuinely disagree", 0),
    ("If it still cannot find enough, it says so honestly — it never makes up an answer", 0),
], size=15, gap=10)

# 7 — Safeguards
s = content("3 · Safeguards", "The guardrails built into the design")
bullets(s, [
    ("Evidence is quoted word-for-word, never summarized — checking a claim against a summary would be circular", 0),
    ("Independence — the model that writes, the models that verify, and the models that grade are all different families, so their biases cannot reinforce each other", 0),
    ("The writer only proposes citations; a separate verifier confirms the source actually supports the claim", 0),
    ("Confidence is calibrated before it is shown, so \"70%\" really means right about 70% of the time", 0),
    ("Every claim is shown — supported, flagged as contested, or marked as a gap — and never silently dropped", 0),
    ("The system cannot \"win\" by quietly deleting hard claims — coverage is tracked", 0),
], size=14.5, gap=10)

# 8 — MVP pipeline
s = content("4 · The pipeline", "From question to evidence-backed report")
pipeline_row(s, ["Question", "Break into sub-questions", "Search (Exa)", "Extract claims", "Verify each claim", "Flag conflicts", "Write report", "Evaluate"],
             top=Inches(1.7), h=Inches(1.05))
_text(s, Inches(0.55), Inches(3.25), Inches(12.2), Inches(0.4),
      [("Planned (not yet in the MVP): when a claim is weak, automatically search again or switch tools before writing the report.", 12.5, GRAY, False, 0)])
table(s, ["What makes it transparent", "What makes it reliable"], [
    ["An evaluation harness that breaks any report into claims and scores them",
     "The verifier labels every claim: supported, refuted, contested, or insufficient"],
    ["Every claim shows its own calibrated confidence score",
     "Conflict detection flags when sources or claims disagree with each other"],
], col_w=[1, 1], fsize=12.5, top=Inches(3.85), height=Inches(2.5))

# 9 — Quick choice: Exa vs Tavily
s = content("5 · Design choices", "Search engine — Exa vs Tavily (12-query bake-off)")
table(s, ["Engine", "recall@k", "relevance", "latency", "panel score"], [
    ["Exa  ✓", "0.33", "0.92", "1.4 s", "0.89"],
    ["Tavily", "0.25", "0.76", "3.5 s", "0.77"],
    ["Semantic Scholar", "0.00", "0.00", "rate-limited", "—"],
], col_w=[2.6, 1.7, 1.7, 1.6, 1.8], fsize=13, top=Inches(1.6), height=Inches(1.9))
bullets(s, [
    ("Exa beat Tavily on every measure — finding the right sources, relevance, and speed (1.4s vs 3.5s)", 0),
    ("Four independent judge-models all preferred Exa's passages", 0),
    ("We use Exa \"highlights\" — short word-for-word excerpts aimed at the question — so citations stay exact and context stays small", 0),
    ("Settled defaults: 5 sources per sub-question, about 2,000 characters each", 0),
], left=Inches(0.55), top=Inches(3.8), size=14.5, gap=10)

# 10 — Quick choice: decomposition
s = content("5 · Design choices", "Breaking the question into sub-questions")
bullets(s, [
    ("We split a question into sub-questions and search each one separately", 0),
    ("This finds 3–4× more distinct, relevant sources than searching the whole question at once", 0),
    ("Example: 8 sources became 27–36, with little overlap — including key papers the broad search missed", 1),
    ("It does not over-split: a simple factual question stays a single search", 0),
], size=15.5, gap=12)

# 11 — Quick choice: claim extraction
s = content("5 · Design choices", "Which model writes the claims")
table(s, ["Model", "Grounding (0–2)", "Atomicity (0–1)", "Note"], [
    ["Llama 4 Maverick (17B)  ✓", "1.24", "0.80", "the smallest model wins the metric that matters most"],
    ["Haiku 4.5", "0.97", "0.74", "dropped"],
    ["Mistral Large 3 (675B)", "0.94", "0.73", "over-reaches — 4× more claims, many unsupported"],
], col_w=[2.8, 1.8, 1.9, 3.9], fsize=12.5, top=Inches(1.6), height=Inches(1.9))
bullets(s, [
    ("Llama produced the best-grounded, most self-contained claims — all three judges agreed", 0),
    ("The much larger Mistral over-reached: it stated confident specifics from memory and stapled a citation on", 0),
    ("So Llama became the writer; Mistral was moved to the verifier panel instead", 0),
], top=Inches(3.8), size=14.5, gap=10)

# 12 — Quick choice: structural formatting
s = content("5 · Design choices", "Keeping formatting out of search")
bullets(s, [
    ("We separate the research question from formatting requests (e.g. \"as a table\", \"include a diagram\")", 0),
    ("Formatting goes only to the report writer — never to search", 0),
    ("So \"add a diagram\" cannot change which sources get retrieved (we verified this)", 1),
    ("The writer produces the prose and any diagram/table; a separate, rule-based step builds the claim table, citations, and disclaimers — so those cannot be paraphrased or invented", 0),
    ("Every sentence in the report must point to a real verified claim — an automatic check flags any that do not", 0),
], size=14.5, gap=10)

# 13 — Pipeline annotated with models
s = content("6 · Models", "The pipeline, with the model behind each step")
pipeline_row(s, ["Question", "Sub-questions", "Search", "Extract claims", "Verify", "Flag conflicts", "Write report"],
             top=Inches(1.7), h=Inches(0.95),
             models=["—", "Llama 4 Maverick", "Exa", "Llama 4 Maverick", "Panel of 3: Sonnet · Mistral · Nova", "verifier panel", "Llama 4 Maverick"])
bullets(s, [
    ("Writer (planning, claim extraction, report) — Llama 4 Maverick", 0),
    ("Verifier — a panel of three different large models (Sonnet, Mistral, Nova) that vote on each claim", 0),
    ("Writer, verifier, and graders are deliberately different model families, so their biases do not line up", 0),
    ("We also trained a small dedicated verifier to potentially replace the three-model panel — next section", 0),
], top=Inches(4.1), size=14, gap=9)

# 14 — Verifier: what it does
s = content("7 · The verifier", "What the verifier does")
bullets(s, [
    ("For each claim, it reads the cited sources and decides: supported, refuted, contested (sources disagree), or insufficient (not enough evidence) — plus a confidence score", 0),
    ("It judges only against the provided evidence — not the model's own background knowledge", 0),
    ("It produces the labels and confidence that make the report transparent and reliable", 0),
    ("Without it, there are no support / contested / gap labels at all", 0),
    ("We test it two ways: on its own (Layer-1), and inside the full pipeline (Layer-2)", 0),
], size=15.5, gap=13)

# 15 — Verifier versions compared
s = content("7 · The verifier", "The four versions we compared")
table(s, ["Version", "What it is", "What it achieves"], [
    ["With verifier", "Full pipeline — three large models check every claim and flag conflicts", "adds honesty labels (supported / contested / gap), but flags too many settled facts as \"contested\""],
    ["Corrected", "Same, with a better conflict-flagging prompt", "keeps the honesty labels and fixes the over-flagging — restoring report quality"],
    ["Without verifier", "Claims shown to the reader unchecked", "baseline — no grounding or honesty labels at all"],
    ["v0 — small trained model", "Fine-tuned DeBERTa-v3 cross-encoder (~184M) on public fact-checking data — FEVER + SciFact", "matches the three-model macro-F1, well-calibrated, ~130× faster and cheaper"],
    ["v1 — small trained model", "Same, plus synthetic hard-negatives and an evidence-ablated curriculum (our pipeline's distribution)", "more cautious — declines to answer when evidence is weak; slightly weaker on the clean test set"],
], col_w=[1.9, 4.3, 4.4], fsize=11.5, top=Inches(1.55), height=Inches(4.2), first_bold=True)

# 16 — Training the small verifier (v0 / v1)
s = content("7 · The verifier — training", "How we trained the small verifier (v0 and v1)")
bullets(s, [
    ("Backbone — a DeBERTa-v3-base cross-encoder (~184M parameters): it reads the (claim, passage) pair together and outputs a 3-way label {supported, refuted, not-enough-info}; 512-token limit", 0),
    ("v0 — supervised fine-tuning on public fact-checking pairs: FEVER (~137k) + SciFact (~2.5k), one (claim, single passage) pair per labelled evidence sentence", 0),
    ("v1 — v0's data plus examples that match our own pipeline's evidence:", 0),
    ("synthetic hard-negatives (607): near-miss false claims written over real retrieved passages, kept only when an independent judge agrees they are not supported", 1),
    ("an evidence-ablated curriculum (~15k): the same claim shown with full / partial / no evidence — teaches it to say \"not-enough-info\" unless the evidence is genuinely sufficient", 1),
    ("Training — 3-way cross-entropy, class-balanced sampling, 3 epochs, learning rate 2e-5, fp16; early-stop on held-out macro-F1; one A100 GPU per model", 0),
    ("Calibration — Platt scaling on the score so confidence is trustworthy", 0),
    ("\"Contested\" is not a training label — the head is 3-way. It is derived at inference (a claim's passages vote both ways). For evaluation we construct contested cases: pair a supported (claim, passage) with a synthesized refuting passage and bundle them into one example whose gold label is contested.", 0),
    ("No leakage — trained only on the FEVER/SciFact train splits and a held-out retrieval pool; never on any evaluation benchmark", 0),
], size=13, gap=7)

# 17 — Benchmarks overview
s = content("7 · Evaluation", "How we test the verifier — two layers")
bullets(s, [
    ("Layer-1 — test the verifier on its own, against labelled fact-checking datasets:", 0),
    ("FEVER (1,000 claims) and SciFact (300 claims), plus a built set of \"contested\" cases", 1),
    ("we measure accuracy, how trustworthy its confidence is, and speed", 1),
    ("Layer-2 — test the verifier inside the full pipeline, scoring finished reports:", 0),
    ("DRA-Bench — our own 250-question benchmark (next slide)", 1),
    ("FRAMES (multi-step questions) and TruthfulQA (common misconceptions)", 1),
    ("We score Perplexity, OpenAI, and a strong Claude-Sonnet reference report through the same harness", 0),
], size=15, gap=10)

# 17 — DRA-Bench (our contribution)
s = content("7 · Evaluation — DRA-Bench  (our contribution)", "DRA-Bench — testing whether the agent is honest")
_text(s, Inches(0.55), Inches(1.32), Inches(12.3), Inches(0.7),
      [("250 questions in 5 types. Each has a \"right behaviour\" label — should the agent answer confidently, flag a genuine disagreement, or admit it cannot tell? This is exactly what existing benchmarks do not measure.", 13.5, GRAY, False, 0)])
table(s, ["Type", "Right behaviour", "What it tests", "Example question"], [
    ["1 · technical", "answer confidently", "answer clearly when the science is settled", "“How does self-attention work in transformer models?”"],
    ["2 · pros & cons", "cover both sides", "give a balanced view of a two-sided question", "“Pros and cons of microservices vs a monolith?”"],
    ["3 · contradictory", "flag the conflict", "surface genuine disagreement between good sources", "“Does moderate alcohol help the heart, or does any amount raise mortality?”"],
    ["4 · unanswerable", "admit it cannot tell", "say so honestly instead of making something up", "“What is the best programming language?”"],
    ["5 · needs a visual", "answer + use the format", "answer and honor a table/diagram request", "“Compare AWS / Azure / GCP in a table.”"],
], col_w=[1.5, 2.0, 3.3, 4.7], fsize=10.5, hsize=11.5, top=Inches(2.15), height=Inches(4.0), first_bold=True)

# 18 — Evaluation metric design
s = content("7 · Evaluation — metrics", "The metrics we designed, and what each one is for")
table(s, ["Metric", "What it tells us"], [
    ["Expected-Behavior Match (EBM) — structural", "Did the report's claim labels do the right thing — flag a real conflict, admit a gap, or answer confidently? Read directly from the labels."],
    ["EBM — text-judge", "Does a judge reading only the report agree it did the right thing? Catches reports honest in the labels but hedged in the prose."],
    ["Grounding rate (+ hallucination, citation P/R)", "Is each claim actually backed by the source it cites? Graded by an independent model, not the verifier itself."],
    ["Relevance (1–5)", "Does the report answer the question asked? Graded by a blind 3-judge panel."],
    ["Quality (1–5)", "Is it clear, well-organized, and complete? Same 3-judge panel."],
    ["Instruction adherence (formatting)", "Did it honor explicit format requests — a table, a diagram, a length limit?"],
    ["Task accuracy + abstention", "For fact-QA: did it reach the right answer — and is a safe \"I don't know\" counted as fine, not wrong?"],
    ["Similarity-to-gold (coverage)", "How many of the facts in a strong reference report did ours include?"],
    ["Calibration (ECE)", "Are the confidence scores trustworthy — does \"70%\" mean right about 70% of the time?"],
], col_w=[3.1, 7.1], fsize=10.5, hsize=12, top=Inches(1.5), height=Inches(5.2), first_bold=True)

# 19 — Layer-1 results
s = content("7 · Evaluation — results", "Layer-1: a small trained verifier matches three large models — ~130× faster")
_text(s, Inches(0.55), Inches(1.3), Inches(12.2), Inches(0.34),
      [("macro-F1 = balanced accuracy · ECE = calibration error (lower is better) · AUROC = ranking quality (higher is better) · combined FEVER+SciFact, n=1,300", 12, GRAY, False, 0)])
table(s, ["Verifier", "macro-F1", "ECE ↓", "AUROC ↑", "latency p50", "speed-up"], [
    ["Three-model LLM panel", "0.815", "0.031", "0.936", "2,485 ms", "1×"],
    ["v0 — DeBERTa-v3 (calibrated)  ✓", "0.839", "0.039", "0.966", "19 ms", "130×"],
    ["v1 — DeBERTa-v3 (calibrated)", "0.834", "0.059", "0.962", "19 ms", "132×"],
], col_w=[3.4, 1.5, 1.4, 1.4, 1.7, 1.3], fsize=12.5, top=Inches(1.75), height=Inches(1.9), first_bold=True)
bullets(s, [
    ("v0 reaches the same macro-F1 as the three-model panel, with comparable calibration (ECE) and stronger ranking (AUROC)", 0),
    ("The decisive win is speed and cost: one small model on our own GPU replaces three large-model calls per claim — about 130× faster", 0),
    ("v1's extra pipeline-distribution training did not help on this clean test set — it is simply more cautious (worse ECE)", 0),
], top=Inches(3.95), size=14, gap=10)

# 20 — Layer-2 results: DRA-Bench, all metrics
s = content("7 · Evaluation — results", "Layer-2: the fix keeps honesty and restores quality")
_text(s, Inches(0.55), Inches(1.32), Inches(12.2), Inches(0.34),
      [("Three versions of the full pipeline — verifier ON (\"with\"), OFF (\"without\"), and the improved version (\"corrected\").", 12.5, GRAY, False, 0)])
table(s, ["Metric (DRA-Bench)", "with", "without", "corrected"], [
    ["EBM — structural (from claim labels)", "0.81", "0.60", "0.79"],
    ["EBM — text-judge (from the report)", "0.79", "0.81", "0.79"],
    ["grounding rate", "0.96", "0.96", "0.95"],
    ["hallucination rate", "0.03", "0.02", "0.03"],
    ["relevance (1–5)", "4.63", "4.73", "4.66"],
    ["quality (1–5)", "3.90", "4.12", "4.11"],
    ["instruction adherence (formatting)", "1.00", "1.00", "1.00"],
], col_w=[3.7, 1.2, 1.2, 1.4], fsize=12, top=Inches(1.7), height=Inches(3.1), first_bold=True)
bullets(s, [
    ("Verifier ON adds the honesty signal (structural EBM 0.81 vs 0.60) — but the original version over-flagged settled facts as \"contested\", which lowered quality", 0),
    ("The corrected version keeps that honesty (structural EBM ≈ \"with\") and recovers quality to the level of \"without\" — significance on the next slide", 0),
    ("Text-judge EBM and grounding barely move across versions — the honesty gain doesn't fully reach the prose, and grounding is bounded by retrieval, not the verifier", 0),
], top=Inches(5.05), size=12.5, gap=7)

# 21 — Significance testing
s = content("7 · Evaluation — results", "Significance testing (DRA-Bench, paired)")
_text(s, Inches(0.55), Inches(1.3), Inches(12.2), Inches(0.5),
      [("Paired tests across the three pipeline versions — paired-t for 1–5 scores, McNemar for pass/fail labels — with Holm correction for multiple comparisons.  p_adj = adjusted p-value.", 12, GRAY, False, 0)])
table(s, ["Comparison", "Metric", "Effect", "Test", "Significant?"], [
    ["corrected vs with", "quality (1–5)", "+0.18", "paired-t", "yes  (p_adj = 7×10⁻⁶)"],
    ["corrected vs with", "EBM — structural", "≈ equal", "McNemar", "no"],
    ["corrected vs without", "EBM — structural", "+0.21", "McNemar", "yes  (p_adj = 8×10⁻¹¹)"],
    ["with vs without", "quality (1–5)", "−0.17", "paired-t", "yes"],
    ["with vs without", "relevance (1–5)", "−0.09", "paired-t", "yes (marginal)"],
    ["all three", "EBM — text-judge", "no difference", "McNemar", "no"],
    ["all three", "grounding rate", "≈ 0", "paired-t", "no"],
], col_w=[2.4, 2.3, 1.8, 1.3, 2.8], fsize=11.5, top=Inches(1.85), height=Inches(3.2), first_bold=True)
bullets(s, [
    ("The corrected fix is real — the quality gain over the over-flagging version is statistically significant, while the honesty signal (structural EBM) is preserved", 0),
    ("The verifier's honesty signal is significant (structural EBM: with / corrected ≫ without); its text-judge and grounding effects are not — the same picture on all three benchmarks", 0),
], top=Inches(5.25), size=12.5, gap=8)

# 22 — Layer-2: DRA-Bench baselines (writing quality / format)
s = content("7 · Evaluation — results", "Layer-2: vs Perplexity & OpenAI (DRA-Bench)")
table(s, ["System (DRA-Bench)", "Relevance", "Quality", "Follows format", "Honesty (text)"], [
    ["Ours (corrected)", "4.66", "4.11", "1.00", "0.79"],
    ["Perplexity", "4.74", "4.94", "0.60", "0.86"],
    ["OpenAI (search)", "4.58", "4.46", "0.60", "0.84"],
    ["Claude Sonnet reference (ceiling)", "4.85", "4.90", "0.60", "—"],
], col_w=[3.6, 1.5, 1.4, 1.7, 1.6], fsize=12.5, top=Inches(1.7), height=Inches(2.3), first_bold=True)
bullets(s, [
    ("Perplexity and OpenAI score a little higher on writing quality — confident, fluent prose", 0),
    ("We clearly lead on following format instructions (1.00 vs 0.60)", 0),
    ("And we expose per-claim grounding that a black-box system can't be measured on — our differentiator", 0),
], top=Inches(4.3), size=14, gap=10)

# 22 — Layer-2: FRAMES + TruthfulQA answer accuracy
s = content("7 · Evaluation — results", "Layer-2: answer accuracy vs Perplexity & OpenAI")
_text(s, Inches(0.55), Inches(1.32), Inches(12.2), Inches(0.34),
      [("FRAMES = multi-step factual questions. TruthfulQA = questions built around common misconceptions. 100 questions each.", 12.5, GRAY, False, 0)])
table(s, ["System", "FRAMES — accuracy", "FRAMES — quality", "TruthfulQA — accuracy", "TruthfulQA — quality"], [
    ["Ours (corrected)", "0.25", "3.44", "0.02", "4.05"],
    ["Perplexity", "0.24", "3.83", "0.06", "4.76"],
    ["OpenAI (search)", "0.37", "4.26", "0.05", "4.33"],
], col_w=[2.6, 2.0, 1.9, 2.2, 2.0], fsize=12.5, top=Inches(1.8), height=Inches(1.7), first_bold=True)
bullets(s, [
    ("Multi-step questions (FRAMES): our accuracy (~25%) matches Perplexity (24%) and trails OpenAI's search model (37%)", 0),
    ("Misconception questions (TruthfulQA): every system scores near zero — being well-grounded in sources does not make the popular answer true", 0),
    ("As on DRA-Bench, the commercial systems write more fluently (higher quality scores)", 0),
], top=Inches(3.9), size=14, gap=10)

# 23 — Layer-2: coverage vs Sonnet reference (detailed)
s = content("7 · Evaluation — results", "Coverage gap vs a strong reference report")
_text(s, Inches(0.55), Inches(1.32), Inches(12.2), Inches(0.5),
      [("We compared our reports to reference reports written by Claude Sonnet for the same 237 DRA-Bench questions, counting how many of the reference's facts our reports also contain.", 13, GRAY, False, 0)])
# three stat boxes
for i, (big, small, fill) in enumerate([
    ("28,794", "facts in the Sonnet reference reports  (~121 per report)", NAVY),
    ("2,895", "of those facts covered by our pipeline", ACCENT),
    ("~10%", "coverage", ACC_DK),
]):
    l = Inches(0.55) + i * Inches(4.15)
    _box(s, l, Inches(2.15), Inches(3.85), Inches(1.7), fill=fill)
    _text(s, l, Inches(2.35), Inches(3.85), Inches(0.8), [(big, 40, WHITE, True, 0)], align=PP_ALIGN.CENTER)
    _text(s, l + Inches(0.25), Inches(3.2), Inches(3.35), Inches(0.6), [(small, 12, WHITE, False, 0)], align=PP_ALIGN.CENTER)
bullets(s, [
    ("So our reports miss roughly 90% of the facts a strong reference report includes", 0),
    ("This is the same with or without the verifier — so it is NOT a verifier problem", 0),
    ("It is a search-breadth gap: a single search engine doesn't fetch enough distinct sources, and fetching deeper from the same engine doesn't help", 0),
    ("The fix is better, more diverse search — the clearest next step", 0),
], top=Inches(4.25), size=14, gap=10)

# 22 — v0/v1 Layer-2 (pending)
s = content("7 · Evaluation — results", "Putting the small trained verifiers in the pipeline (in progress)")
_box(s, Inches(0.55), Inches(1.7), Inches(12.2), Inches(1.15), fill=LIGHT, line=AMBER, line_w=Pt(1.5))
_text(s, Inches(0.8), Inches(1.95), Inches(11.7), Inches(0.7), [
    [("Running now — ", 15, AMBER, True, 0),
     ("we are putting the two small trained verifiers (v0 and v1) into the full pipeline and scoring them on all three benchmarks.", 15, INK, False, 0)]])
bullets(s, [
    ("The question: does v0, the Layer-1 winner, also win inside the full pipeline?", 0),
    ("And does v1's extra caution — which looked like a weakness on clean tests — actually help on the messier evidence the real pipeline retrieves?", 0),
    ("Required fix already shipped: the small verifier no longer mislabels a well-supported claim as \"contested\" just because one of several sources disagrees", 0),
    ("Results will fill in this slide when the run finishes", 1),
], top=Inches(3.25), size=14.5, gap=11)

# 23 — Key learnings
s = content("7 · The verifier", "Key learnings")
bullets(s, [
    ("The verifier is essential — it is the only source of support / contested / gap labels", 0),
    ("The conflict-flagging step is needed but tends to over-flag; a better prompt fixes that without removing it", 0),
    ("Honesty in the data does not automatically reach the reader — the wording has to reflect it too", 0),
    ("Grounding is limited by search, not the verifier — this is the real ceiling", 0),
    ("A small trained verifier can match a three-model panel at far lower cost — a practical, cheaper replacement", 0),
    ("A more cautious verifier looks worse on clean tests but may be better on real, messy evidence (testing now)", 0),
], size=14.5, gap=11)

# 24 — Limitations 1
s = content("8 · Limitations", "Known limitations (1 / 2)")
bullets(s, [
    ("Many smaller design choices were tested on small samples — directional, not statistically proven", 0),
    ("The verifier checks that a claim matches its source, not whether the source itself is trustworthy", 0),
    ("Tested only on English, text-only questions", 0),
    ("Search settings are fixed; the MVP does not yet adapt them per question", 0),
    ("Coverage tops out around 80–85% because we use a single search engine — fetching deeper does not help", 0),
], size=15, gap=12)

# 25 — Limitations 2
s = content("8 · Limitations", "Known limitations (2 / 2)")
bullets(s, [
    ("The Layer-1 fact-checking benchmarks are cleaner and easier than real multi-source evidence — so those scores are optimistic", 0),
    ("Adding a formatting request can slightly reword what is sent to search, so two versions of a question are not perfectly identical", 0),
    ("Our reference reports and some judges are both Claude-family — a mild bias on the writing-quality scores (grounding is judged by a different family)", 0),
    ("The big one: the verifier and conflict steps can only be as good as the evidence retrieved — the ceiling is search", 0),
], size=14.5, gap=12)

# 26 — Future exploration
s = content("9 · What's next", "Where this goes next")
bullets(s, [
    ("Better search — multiple search engines, weighting more credible sources, and routing by question type. This is the lever that actually raises the ceiling.", 0),
    ("Support non-English and non-text (image / table) inputs", 0),
    ("Use the verifier to train an automatic \"search-again\" controller:", 0),
    ("the verifier scores whether each extra search step improved the evidence, and a small model learns the best next move", 1),
    ("before trusting it: check that better evidence really does raise its score, and that it cannot be gamed", 1),
    ("limit: this still cannot beat the search ceiling — if the evidence is not out there, searching smarter does not help", 1),
    ("Also: automatic prompt tuning, and training one smaller, faster model to imitate the whole pipeline", 0),
], size=14.5, gap=9)

# 27 — Closing
s = prs.slides.add_slide(BLANK)
_box(s, 0, 0, EMU_W, EMU_H, fill=NAVY)
_box(s, Inches(0.9), Inches(2.3), Inches(0.18), Inches(2.4), fill=ACCENT)
_text(s, Inches(1.25), Inches(2.2), Inches(11), Inches(1.0),
      [("Trust you can measure is the real blocker", 32, WHITE, True, 0)])
_text(s, Inches(1.28), Inches(3.4), Inches(11.4), Inches(2.6), [
    [("Check every claim, score confidence you can trust, and search again when evidence is weak —", 17, RGBColor(0xCF,0xDF,0xEA), False, 0)],
    [("that is how you tell plausible apart from correct.", 17, RGBColor(0xCF,0xDF,0xEA), False, 0)],
    [(" ", 8, WHITE, False, 0)],
    [("The verifier is the backbone — and a small trained model can do its job far more cheaply.", 17, WHITE, True, 0)],
    [("The ceiling we hit is search — and that is exactly where we go next.", 17, WHITE, True, 0)],
])
_text(s, Inches(1.28), Inches(6.4), Inches(11), Inches(0.5),
      [("Thank you  ·  Neha Anna John", 15, RGBColor(0x9F,0xB4,0xC4), False, 0)])

out = os.path.expanduser("~/Desktop/DeepResearchAgent_Presentation.pptx")
prs.save(out)
print(f"saved {len(prs.slides._sldIdLst)} slides -> {out}")
