"""Hand-authored planning blocks for the demo replay — the one piece of stage data
that the composed sample reports in ``docs/sample_reports/`` do not contain.

The pipeline's planner does two things the final report never persists: it splits the
raw query into a *resolved brief* + presentation *constraints* (``wants_visual`` /
``format`` / ``focus``), and it decomposes the core query into sub-questions, each routed
to a retrieval tool. Everything downstream (sources, claims, verdicts, confidence,
contradictions, narrative) IS recoverable from the report markdown and is parsed straight
from it — see ``build_fixtures.py``. Only these planner outputs are reconstructed here.

These decompositions are faithful to each query (the type-5 ``table`` constraint, for
instance, is stated verbatim in the query) and are labelled in the UI as "the planner's
decomposition" — they are not presented as captured runtime output. Keyed by report slug.
"""
from __future__ import annotations

# route is a label only — Exa is the single MVP retrieval backend (see dra.router /
# dra.loop). "academic" vs "web" mirrors what the router would tag each sub-question.
PLAN_BLOCKS: dict[str, dict] = {
    "mamba-state-space-models_deep-NLP": {
        "resolved_brief": (
            "Explain the mechanisms by which state space models such as Mamba reach "
            "transformer-level quality, and characterise their limitations on tasks that "
            "demand precise in-context recall."
        ),
        "constraints": {"wants_visual": False, "format": "prose",
                        "focus": "enabling mechanisms + in-context-recall limitations"},
        "subquestions": [
            {"text": "What mechanisms allow state space models like Mamba to match transformer quality?",
             "route": "academic"},
            {"text": "How do Mamba's selective state-space layers relate to attention?",
             "route": "academic"},
            {"text": "What are the limitations of SSMs on tasks requiring precise in-context recall?",
             "route": "academic"},
        ],
    },
    "data-localization-laws_pros-and-cons": {
        "resolved_brief": (
            "Weigh the advantages against the disadvantages of mandatory data-localization "
            "laws for multinational technology companies, including their economic impact."
        ),
        "constraints": {"wants_visual": False, "format": "prose",
                        "focus": "balanced pros and cons + economic impact"},
        "subquestions": [
            {"text": "What are the advantages of mandatory data localization laws for multinational tech companies?",
             "route": "web"},
            {"text": "What are the disadvantages of mandatory data localization laws for multinational tech companies?",
             "route": "web"},
            {"text": "What are the economic impacts of data localization measures?",
             "route": "web"},
        ],
    },
    "alcohol-and-cardiovascular-health_contested": {
        "resolved_brief": (
            "Determine whether moderate alcohol consumption confers cardiovascular benefit "
            "or whether any amount raises mortality risk — surfacing the disagreement between "
            "credible sources rather than forcing a single answer."
        ),
        "constraints": {"wants_visual": False, "format": "prose",
                        "focus": "contested benefit-vs-mortality evidence"},
        "subquestions": [
            {"text": "Does moderate alcohol consumption provide cardiovascular health benefits?",
             "route": "academic"},
            {"text": "Does any amount of alcohol consumption increase mortality risk?",
             "route": "academic"},
        ],
    },
    "best-programming-language_no-answer": {
        "resolved_brief": (
            "Address 'what is the best programming language?' — a question with no single "
            "correct answer; report the evaluation criteria and task-dependence instead of "
            "inventing a winner."
        ),
        "constraints": {"wants_visual": False, "format": "prose",
                        "focus": "evaluation criteria + task-dependent suitability"},
        "subquestions": [
            {"text": "What are the most popular programming languages?", "route": "web"},
            {"text": "What criteria are used to evaluate programming languages?", "route": "web"},
            {"text": "Which languages are preferred for specific tasks (AI/ML, web, enterprise, infra)?",
             "route": "web"},
        ],
    },
    "cloud-providers-aws-azure-gcp_multi-format": {
        "resolved_brief": (
            "Compare AWS, Azure, and GCP across compute, storage, networking, and pricing "
            "models, and present the comparison as a structured table."
        ),
        "constraints": {"wants_visual": True, "format": "table",
                        "focus": "compute · storage · networking · pricing"},
        "subquestions": [
            {"text": "Compare AWS, Azure, and GCP compute services.", "route": "web"},
            {"text": "Compare AWS, Azure, and GCP storage services.", "route": "web"},
            {"text": "Compare AWS, Azure, and GCP networking services.", "route": "web"},
            {"text": "Compare AWS, Azure, and GCP pricing models.", "route": "web"},
        ],
    },
}

# Type metadata (DRA-Bench question type → display label), keyed by slug.
TYPE_META: dict[str, dict] = {
    "mamba-state-space-models_deep-NLP": {"type": 1, "label": "technical · answer confidently"},
    "data-localization-laws_pros-and-cons": {"type": 2, "label": "pros & cons · cover both sides"},
    "alcohol-and-cardiovascular-health_contested": {"type": 3, "label": "contradictory · flag the conflict"},
    "best-programming-language_no-answer": {"type": 4, "label": "unanswerable · admit it cannot tell"},
    "cloud-providers-aws-azure-gcp_multi-format": {"type": 5, "label": "needs a visual · answer + use the format"},
}
