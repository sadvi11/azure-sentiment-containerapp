# Convenience commands. Run `make help` to list them.
IMAGE ?= sentiment-api:latest
RG    ?= sentiment-rg
ACR   ?= your-unique-acr-name
LOC   ?= canadacentral

.PHONY: help install train test run docker-build docker-run \
        azure-build azure-deploy clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Install Python deps + dev tools
	pip install -r app/requirements.txt pytest httpx

train: ## Train the model artifact
	python -m app.train

test: ## Run the test suite
	pytest -q

run: ## Run the API locally on :8000
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

docker-build: ## Build the Docker image locally
	docker build -t $(IMAGE) .

docker-run: ## Run the container locally on :8000
	docker run --rm -p 8000:8000 $(IMAGE)

azure-build: ## Build & push the image in Azure Container Registry
	az acr build --registry $(ACR) --image sentiment-api:v1 .

azure-deploy: ## Deploy infra + app with Bicep (see infra/README.md)
	az deployment group create -g $(RG) --template-file infra/main.bicep \
	  --parameters appName=sentiment-api

clean: ## Remove local model artifact and caches
	rm -f app/model.joblib
	find . -type d -name __pycache__ -exec rm -rf {} +
