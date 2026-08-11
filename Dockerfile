# syntax=docker/dockerfile:1

# ---- Stage 1: build dependencies and train the model ----
FROM python:3.11-slim AS builder

WORKDIR /build

# Install dependencies into a virtualenv we can copy to the final image.
COPY app/requirements.txt .
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install --no-cache-dir -r requirements.txt

# Copy source and train the model artifact at build time.
COPY app ./app
RUN python -m app.train


# ---- Stage 2: minimal runtime image ----
FROM python:3.11-slim AS runtime

# Run as a non-root user (container hardening best practice).
RUN useradd --create-home --uid 10001 appuser

WORKDIR /app

# Bring over the prepared virtualenv and the trained code + model.
COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /build/app ./app
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER appuser

EXPOSE 8000

# Basic container-level healthcheck (Container Apps probes are the real gate).
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
