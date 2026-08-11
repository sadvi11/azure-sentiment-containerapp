"""FastAPI service that serves the sentiment model.

Endpoints:
  GET  /            - service metadata
  GET  /health      - liveness/readiness probe target for Container Apps
  POST /predict     - run inference on a piece of text
  GET  /metrics     - Prometheus metrics (added by the instrumentator)
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, Field

from app.model import load_model, predict


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the model at startup so the first request is not slow.
    load_model()
    yield


app = FastAPI(
    title="Sentiment Analysis API",
    description="A scikit-learn sentiment model served on Azure Container Apps.",
    version="1.0.0",
    lifespan=lifespan,
)

# Expose Prometheus metrics at /metrics for Grafana dashboards + HPA signals.
Instrumentator().instrument(app).expose(app)


class PredictRequest(BaseModel):
    text: str = Field(..., min_length=1, examples=["this deployment worked perfectly"])


class PredictResponse(BaseModel):
    text: str
    label: str
    confidence: float


@app.get("/")
def root() -> dict:
    return {
        "service": "sentiment-analysis-api",
        "version": "1.0.0",
        "endpoints": ["/health", "/predict", "/metrics"],
    }


@app.get("/health")
def health() -> dict:
    """Container Apps probes hit this. Confirm the model is loadable."""
    load_model()
    return {"status": "healthy"}


@app.post("/predict", response_model=PredictResponse)
def predict_sentiment(request: PredictRequest) -> PredictResponse:
    result = predict(request.text)
    return PredictResponse(
        text=request.text,
        label=result["label"],
        confidence=result["confidence"],
    )
