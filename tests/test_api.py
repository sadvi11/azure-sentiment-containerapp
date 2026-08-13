"""API tests. These run in CI before the Docker image is built.

The model is trained once in a fixture so tests exercise the real
train -> load -> serve path.
"""
import os

import pytest
from fastapi.testclient import TestClient

from app.train import train


@pytest.fixture(scope="session", autouse=True)
def trained_model():
    """Ensure a model artifact exists before the app loads it."""
    if not os.path.exists(
        os.path.join(os.path.dirname(__file__), "..", "app", "model.joblib")
    ):
        train()
    yield


@pytest.fixture(scope="session")
def client(trained_model):
    from app.main import app

    with TestClient(app) as c:
        yield c


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_root(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["service"] == "sentiment-analysis-api"


def test_predict_positive(client):
    response = client.post("/predict", json={"text": "strong growth and improving margins"})
    assert response.status_code == 200
    body = response.json()
    assert body["label"] == "positive"
    assert 0.0 <= body["confidence"] <= 1.0


def test_predict_negative(client):
    response = client.post("/predict", json={"text": "weak results and a disappointing outlook"})
    assert response.status_code == 200
    assert response.json()["label"] == "negative"


def test_predict_rejects_empty(client):
    response = client.post("/predict", json={"text": ""})
    assert response.status_code == 422  # validation error


# --- Regression tests for the silent-wrong-answer bug ----------------------
#
# The deployed model was trained on product-review text and asked about
# financial results. Every financial term was out of vocabulary, so it returned
# a real-looking label at ~0.52 confidence and got 2 of 6 right. Nothing
# errored, so CI stayed green and the endpoint stayed wrong.
#
# These tests exist so that failure cannot come back unnoticed.


@pytest.mark.parametrize(
    "text,expected",
    [
        ("record profits and revenue beat expectations", "positive"),
        ("losses widened and the outlook was cut", "negative"),
        ("earnings surged and margins improved", "positive"),
        ("revenue missed estimates and guidance was lowered", "negative"),
        ("shares plunged after a disappointing quarter", "negative"),
        ("strong growth and management raised guidance", "positive"),
    ],
)
def test_financial_sentences_are_classified_correctly(client, text, expected):
    """The exact domain that was silently failing in production."""
    body = client.post("/predict", json={"text": text}).json()
    assert body["label"] == expected, (
        f"{text!r} -> {body['label']} at {body['confidence']} "
        f"(coverage {body['vocab_coverage']})"
    )


@pytest.mark.parametrize(
    "text",
    [
        "zorblax quixotic fnord wibble",   # nonsense
        "le chat est sur la table",        # another language
        "12345 67890",                     # no words at all
    ],
)
def test_out_of_vocabulary_input_abstains(client, text):
    """Unknown vocabulary must produce "uncertain", never a guess.

    Without this the model returns the class prior dressed up as a prediction.
    """
    body = client.post("/predict", json={"text": text}).json()
    assert body["label"] == "uncertain"
    assert body["vocab_coverage"] < 0.30
    assert "reason" in body


def test_prediction_reports_its_own_grounding(client):
    """Every response must carry the coverage numbers behind it.

    A label with no indication of how much the model recognised is exactly
    what made the original failure invisible.
    """
    body = client.post("/predict", json={"text": "strong growth this quarter"}).json()
    for field in ("label", "confidence", "vocab_coverage", "known_terms", "total_terms"):
        assert field in body, f"missing {field}"
    assert body["known_terms"] <= body["total_terms"]


def test_confident_answers_are_never_coin_flips(client):
    """If it commits to a label, it must clear the confidence floor.

    The original model answered "positive" at 0.52 - technically a prediction,
    practically a coin toss presented as an answer.
    """
    from app.model import MIN_CONFIDENCE

    for text in ["strong growth and improving margins", "weak results and rising losses"]:
        body = client.post("/predict", json={"text": text}).json()
        if body["label"] != "uncertain":
            assert body["confidence"] >= MIN_CONFIDENCE


def test_metrics_exposed(client):
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "http_request" in response.text
