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
    response = client.post("/predict", json={"text": "this is amazing and works perfectly"})
    assert response.status_code == 200
    body = response.json()
    assert body["label"] == "positive"
    assert 0.0 <= body["confidence"] <= 1.0


def test_predict_negative(client):
    response = client.post("/predict", json={"text": "terrible and broke after one day"})
    assert response.status_code == 200
    assert response.json()["label"] == "negative"


def test_predict_rejects_empty(client):
    response = client.post("/predict", json={"text": ""})
    assert response.status_code == 422  # validation error


def test_metrics_exposed(client):
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "http_request" in response.text
