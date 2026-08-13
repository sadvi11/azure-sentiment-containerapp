"""Train the sentiment model and save it to disk.

Run locally or at Docker build time:

    python -m app.train

Produces app/model.joblib, a scikit-learn Pipeline (TF-IDF + Logistic
Regression). Serving code loads this artifact - training and serving are
separate steps, exactly like a real MLOps workflow.

Training prints two numbers on purpose:

  * cross-validated accuracy on the generated training set, which mostly
    confirms the model learned the lexicon and is not a claim about the
    real world;
  * accuracy on a hand-written held-out set the generator never produced,
    which is the number actually worth quoting.

Printing only the first would be the flattering choice and would hide exactly
the failure this model already had once - see the note at the top of data.py.
"""
import os

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.pipeline import Pipeline

from app.data import HELDOUT_EXAMPLES, TRAINING_DATA

MODEL_PATH = os.path.join(os.path.dirname(__file__), "model.joblib")

# Unigrams only. Bigrams on this data produced mostly single-document features,
# which memorise instead of generalising - measured at 0.471 CV accuracy, worse
# than random, while looking perfect on the training sentences themselves.
VECTORIZER_KWARGS = dict(ngram_range=(1, 1), min_df=2)


def build_pipeline() -> Pipeline:
    """Return an untrained TF-IDF + LogisticRegression pipeline."""
    return Pipeline(
        [
            ("tfidf", TfidfVectorizer(**VECTORIZER_KWARGS)),
            ("clf", LogisticRegression(max_iter=1000)),
        ]
    )


def evaluate(pipeline: Pipeline) -> dict:
    """Score the pipeline both ways and return the metrics."""
    texts = [text for text, _ in TRAINING_DATA]
    labels = [label for _, label in TRAINING_DATA]

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_accuracy = cross_val_score(
        build_pipeline(), texts, labels, cv=cv, scoring="accuracy"
    ).mean()

    heldout_texts = [text for text, _ in HELDOUT_EXAMPLES]
    heldout_labels = [label for _, label in HELDOUT_EXAMPLES]
    heldout_accuracy = pipeline.score(heldout_texts, heldout_labels)

    return {
        "cv_accuracy": float(cv_accuracy),
        "heldout_accuracy": float(heldout_accuracy),
        "n_train": len(TRAINING_DATA),
        "n_heldout": len(HELDOUT_EXAMPLES),
    }


def train(model_path: str = MODEL_PATH) -> Pipeline:
    """Train on the generated dataset and persist the model artifact."""
    texts = [text for text, _ in TRAINING_DATA]
    labels = [label for _, label in TRAINING_DATA]

    pipeline = build_pipeline()
    pipeline.fit(texts, labels)

    joblib.dump(pipeline, model_path)

    metrics = evaluate(pipeline)
    print(f"Trained on {metrics['n_train']} samples -> {model_path}")
    print(
        f"  cross-validated accuracy (generated data): "
        f"{metrics['cv_accuracy']:.3f}  <- confirms the lexicon was learned"
    )
    print(
        f"  held-out accuracy ({metrics['n_heldout']} hand-written sentences): "
        f"{metrics['heldout_accuracy']:.3f}  <- the number that matters"
    )
    return pipeline


if __name__ == "__main__":
    train()
