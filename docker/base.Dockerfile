# Shared base image for all SAGE Python services.
# Installs all non-GPU dependencies once; GPU build is in scenario_agent.Dockerfile.
FROM python:3.11-slim

WORKDIR /app

# System deps needed by some Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libffi-dev curl \
    && rm -rf /var/lib/apt/lists/*

# Copy project descriptor and install dependencies first (layer cache)
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]" || pip install --no-cache-dir \
    "graphiti-core[falkordb]" pydantic boto3 redis fastapi uvicorn langgraph \
    langchain-core numpy scipy scikit-learn ortools yfinance h3 websockets \
    apscheduler shap

# Copy source last so code changes don't bust the dep cache
COPY contracts/    contracts/
COPY knowledge/    knowledge/
COPY orchestration/ orchestration/
COPY sensory_agent/ sensory_agent/
COPY scenario_agent/ scenario_agent/
COPY alt_procurement_agent/ alt_procurement_agent/
COPY reserve_optim_agent/ reserve_optim_agent/
COPY visualizer_agent/ visualizer_agent/
COPY demo_cache/   demo_cache/
# scripts + data bundle + env loader so the container can self-seed the graph
# (docker compose exec sage-core python -m scripts.seed_kb) with the SAME
# graphiti-core version that reads it — avoids cross-version schema mismatches.
COPY scripts/      scripts/
COPY data/         data/
COPY config_env.py .

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
