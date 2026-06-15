"""Torch model-binding for the trained cross-encoder verifier (Verifier B).

Loads a fine-tuned DeBERTa checkpoint and returns a
`score_fn(claim, passage) -> {"supported": p, "refuted": p, "nei": p}` for
injection into `CrossEncoderVerifier`. This is the piece that lets `dra` run the
*trained* verifier end-to-end.

torch + transformers are imported **lazily** inside `bind_score_fn`, so importing
`dra.verify` (and the LLM-judge path) stays torch-free — only callers that
actually run the cross-encoder pull in the heavy deps.
"""
from __future__ import annotations

MAX_LEN = 512


def bind_score_fn(ckpt: str, device: str = "cuda"):
    """Return a `score_fn(claim, passage) -> {label: prob}` backed by the
    fine-tuned cross-encoder checkpoint at `ckpt`. Lazy torch/transformers import."""
    import torch
    import torch.nn.functional as F
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    from dra.verify.train import ID2LABEL

    tok = AutoTokenizer.from_pretrained(ckpt)
    model = AutoModelForSequenceClassification.from_pretrained(ckpt).to(device).eval()

    @torch.no_grad()
    def score_fn(claim, passage):
        enc = tok(claim, passage, truncation="only_second", max_length=MAX_LEN,
                  return_tensors="pt").to(device)
        probs = F.softmax(model(**enc).logits, dim=-1)[0].tolist()
        return {ID2LABEL[i]: probs[i] for i in range(3)}

    return score_fn
