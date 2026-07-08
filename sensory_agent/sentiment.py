"""
Sentiment analysis module using HuggingFace ``tabularisai/multilingual-sentiment-analysis``.

Maps 5-class sentiment to risk labels:
  0 → "Highly Risky"   (Very Negative)
  1 → "Risky"          (Negative)
  2 → "Satisfactory"   (Neutral)
  3 → "Safe"           (Positive)
  4 → "Completely Safe" (Very Positive)

Also exposes ``sentiment_to_severity()`` which converts sentiment labels
to a 0–1 severity float compatible with the SAGE fusion pipeline.
"""
from __future__ import annotations

import logging
from functools import lru_cache

log = logging.getLogger(__name__)

# Sentiment label → SAGE severity (0–1, higher = more risk)
SENTIMENT_SEVERITY_MAP = {
    "Highly Risky":    0.95,
    "Risky":           0.75,
    "Satisfactory":    0.40,
    "Safe":            0.15,
    "Completely Safe":  0.05,
}

SENTIMENT_MAP = {
    0: "Highly Risky",
    1: "Risky",
    2: "Satisfactory",
    3: "Safe",
    4: "Completely Safe",
}


@lru_cache(maxsize=1)
def _load_model():
    """
    Lazy-load the HuggingFace sentiment model.
    Cached so it's only loaded once per process lifetime.
    """
    try:
        from transformers import AutoTokenizer, AutoModelForSequenceClassification
        model_name = "tabularisai/multilingual-sentiment-analysis"
        log.info("Loading sentiment model: %s", model_name)
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSequenceClassification.from_pretrained(model_name)
        model.eval()  # inference mode
        log.info("Sentiment model loaded successfully")
        return tokenizer, model
    except Exception as exc:
        log.error("Failed to load sentiment model: %s", exc)
        raise


def predict_sentiment(texts: list[str] | str) -> list[str]:
    """
    Predict sentiment for one or more texts.

    Args:
        texts: A single string or list of strings to analyse.

    Returns:
        List of sentiment labels: "Highly Risky", "Risky",
        "Satisfactory", "Safe", or "Completely Safe".
    """
    import torch

    if isinstance(texts, str):
        texts = [texts]

    tokenizer, model = _load_model()
    inputs = tokenizer(
        texts,
        return_tensors="pt",
        truncation=True,
        padding=True,
        max_length=512,
    )
    with torch.no_grad():
        outputs = model(**inputs)

    probabilities = torch.nn.functional.softmax(outputs.logits, dim=-1)
    predictions = torch.argmax(probabilities, dim=-1).tolist()
    return [SENTIMENT_MAP[p] for p in predictions]


def sentiment_to_severity(label: str) -> float:
    """
    Convert a sentiment label to a 0–1 severity score for the fusion pipeline.
    Higher = more risk. Used as the ``severity`` field in news/GDELT payloads.
    """
    return SENTIMENT_SEVERITY_MAP.get(label, 0.40)


def predict_severity(text: str) -> float:
    """
    One-shot helper: predict sentiment for a single text and return severity.
    """
    labels = predict_sentiment(text)
    return sentiment_to_severity(labels[0])


def predict_tone(text: str) -> float:
    """
    Predict a GDELT-style tone score from sentiment.
    Negative = hostile, positive = cooperative.
    Maps:  Highly Risky → -8.0, Risky → -4.0, Satisfactory → 0.0,
           Safe → +4.0, Completely Safe → +8.0
    """
    TONE_MAP = {
        "Highly Risky":     -8.0,
        "Risky":            -4.0,
        "Satisfactory":      0.0,
        "Safe":              4.0,
        "Completely Safe":   8.0,
    }
    labels = predict_sentiment(text)
    return TONE_MAP.get(labels[0], 0.0)
