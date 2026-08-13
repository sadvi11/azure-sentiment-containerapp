"""FastAPI service that serves the sentiment model.

Endpoints:
  GET  /            - service metadata
  GET  /health      - liveness/readiness probe target for Container Apps
  POST /predict     - run inference on a piece of text
  GET  /metrics     - Prometheus metrics (added by the instrumentator)
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_client import GC_COLLECTOR, PLATFORM_COLLECTOR, PROCESS_COLLECTOR, REGISTRY
from prometheus_fastapi_instrumentator import Instrumentator
from pydantic import BaseModel, Field

from app.model import load_model, predict

# On Container Apps /metrics is reachable from the public internet, unlike the
# in-cluster scrape on EKS. prometheus_client registers three collectors by
# default that publish host detail rather than app behaviour -- notably the
# exact interpreter version (python_info -> "3.11.15"), which hands an attacker
# a free CVE lookup. Drop them; the HTTP request metrics we actually want are
# added by the Instrumentator below and are unaffected.
for _collector in (PROCESS_COLLECTOR, PLATFORM_COLLECTOR, GC_COLLECTOR):
    try:
        REGISTRY.unregister(_collector)
    except KeyError:  # already absent, e.g. under a reimport in tests
        pass


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
    text: str = Field(..., min_length=1, examples=["strong growth and improving margins"])


class PredictResponse(BaseModel):
    """Prediction plus the evidence behind it.

    The coverage fields are not decoration. This model previously returned a
    bare label and confidence, and when it was asked about a domain it had
    never been trained on it answered "positive" at 0.52 - indistinguishable,
    from the outside, from a real prediction. Reporting how much of the input
    the model actually recognised is what makes that failure visible instead
    of silent.
    """

    text: str
    label: str  # "positive" | "negative" | "uncertain"
    confidence: float
    vocab_coverage: float  # fraction of input terms the model knows
    known_terms: int
    total_terms: int
    reason: str | None = None  # populated only when label is "uncertain"


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
        vocab_coverage=result["vocab_coverage"],
        known_terms=result["known_terms"],
        total_terms=result["total_terms"],
        reason=result.get("reason"),
    )
