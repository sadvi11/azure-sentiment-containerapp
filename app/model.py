"""Model loading and prediction logic, kept separate from the web layer."""
import os
from functools import lru_cache

import joblib

MODEL_PATH = os.path.join(os.path.dirname(__file__), "model.joblib")

# Human-readable labels for the two classes.
LABELS = {0: "negative", 1: "positive"}


@lru_cache(maxsize=1)
def load_model():
    """Load the trained model once and cache it for the process lifetime."""
    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(
            f"Model artifact not found at {MODEL_PATH}. "
            "Run `python -m app.train` first."
        )
    return joblib.load(MODEL_PATH)


def predict(text: str) -> dict:
    """Return the predicted sentiment label and confidence for `text`."""
    model = load_model()
    prediction = int(model.predict([text])[0])
    # predict_proba gives the confidence for the chosen class.
    probabilities = model.predict_proba([text])[0]
    confidence = float(probabilities[prediction])
    return {
        "label": LABELS[prediction],
        "confidence": round(confidence, 4),
    }
