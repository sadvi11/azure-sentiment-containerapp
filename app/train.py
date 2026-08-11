"""Train the sentiment model and save it to disk.

Run locally or at Docker build time:

    python -m app.train

Produces app/model.joblib, a scikit-learn Pipeline (TF-IDF + Logistic
Regression). Serving code loads this artifact — training and serving are
separate steps, exactly like a real MLOps workflow.
"""
import os

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from app.data import TRAINING_DATA

MODEL_PATH = os.path.join(os.path.dirname(__file__), "model.joblib")


def build_pipeline() -> Pipeline:
    """Return an untrained TF-IDF + LogisticRegression pipeline."""
    return Pipeline(
        [
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=1)),
            ("clf", LogisticRegression(max_iter=1000)),
        ]
    )


def train(model_path: str = MODEL_PATH) -> Pipeline:
    """Train on the embedded dataset and persist the model artifact."""
    texts = [text for text, _ in TRAINING_DATA]
    labels = [label for _, label in TRAINING_DATA]

    pipeline = build_pipeline()
    pipeline.fit(texts, labels)

    joblib.dump(pipeline, model_path)
    print(f"Model trained on {len(texts)} samples and saved to {model_path}")
    return pipeline


if __name__ == "__main__":
    train()
