"""Model loading and prediction logic, kept separate from the web layer."""
import os
from functools import lru_cache

import joblib

MODEL_PATH = os.path.join(os.path.dirname(__file__), "model.joblib")

# Human-readable labels for the two classes.
LABELS = {0: "negative", 1: "positive"}

# --- Abstention thresholds -------------------------------------------------
#
# A TF-IDF model cannot represent a word it never saw in training. Given an
# entirely unfamiliar sentence it produces a near-zero vector, and logistic
# regression then returns the class prior - a real-looking label at roughly
# 0.50 confidence. Nothing errors, so the failure is invisible unless you
# already know the answer.
#
# This is exactly how the deployed version of this service failed: trained on
# product reviews, asked about financial results, and returning coin-flip
# answers that looked like predictions. Retraining on more domains helps, but
# it does not fix the general case - the next unfamiliar domain fails the same
# silent way. So the serving layer measures how much of the input it actually
# recognises and abstains when the answer would not be grounded in anything.
#
# Refusing to answer is a worse demo and a better model.

# Below this fraction of in-vocabulary terms, the prediction is not grounded
# in enough known signal to be meaningful.
MIN_VOCAB_COVERAGE = 0.30

# Even with known words, a probability this close to 0.5 is a coin flip.
MIN_CONFIDENCE = 0.55


@lru_cache(maxsize=1)
def load_model():
    """Load the trained model once and cache it for the process lifetime."""
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(
            f"Model artifact not found at {MODEL_PATH}. "
            "Run `python -m app.train` first."
        )
    return joblib.load(MODEL_PATH)


def _vocab_coverage(model, text: str) -> tuple[float, int, int]:
    """Fraction of the input's words the vectorizer actually knows.

    Returns (coverage, known, total). An empty or all-stopword input counts as
    zero coverage rather than dividing by zero.
    """
    vectorizer = model.named_steps["tfidf"]
    vocabulary = vectorizer.vocabulary_

    # Use the vectorizer's own analyzer so tokenisation matches training
    # exactly - splitting on whitespace here would count "growth," as unknown
    # when the model knows "growth".
    analyzer = vectorizer.build_analyzer()
    # Unigrams only: an unseen bigram of two known words is not evidence of
    # unfamiliar vocabulary, which is what this check is for.
    tokens = [t for t in analyzer(text) if " " not in t]

    if not tokens:
        return 0.0, 0, 0

    known = sum(1 for t in tokens if t in vocabulary)
    return known / len(tokens), known, len(tokens)


def predict(text: str) -> dict:
    """Return the predicted sentiment label and confidence for `text`.

    Returns label "uncertain" when the input is outside the vocabulary the
    model was trained on, or when the decision is too close to call. Callers
    get an explicit "I don't know" instead of a fabricated label.
    """
    model = load_model()

    coverage, known, total = _vocab_coverage(model, text)

    prediction = int(model.predict([text])[0])
    probabilities = model.predict_proba([text])[0]
    confidence = float(probabilities[prediction])

    result = {
        "label": LABELS[prediction],
        "confidence": round(confidence, 4),
        "vocab_coverage": round(coverage, 4),
        "known_terms": known,
        "total_terms": total,
    }

    if coverage < MIN_VOCAB_COVERAGE:
        result["label"] = "uncertain"
        result["reason"] = (
            f"only {known} of {total} terms are in the model's vocabulary "
            f"({coverage:.0%} coverage, minimum {MIN_VOCAB_COVERAGE:.0%}). "
            "This text is outside the domain the model was trained on, so any "
            "label would be a guess rather than a prediction."
        )
    elif confidence < MIN_CONFIDENCE:
        result["label"] = "uncertain"
        result["reason"] = (
            f"confidence {confidence:.2f} is below the {MIN_CONFIDENCE:.2f} "
            "threshold - the model does not separate the classes well enough "
            "on this input to commit to an answer."
        )

    return result
