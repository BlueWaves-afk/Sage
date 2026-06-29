FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir \
    "graphiti-core[falkordb]" pydantic boto3 redis \
    langgraph langchain-core numpy scikit-learn shap

COPY contracts/     contracts/
COPY knowledge/     knowledge/
COPY orchestration/ orchestration/
COPY sensory_agent/ sensory_agent/
COPY demo_cache/    demo_cache/

RUN mkdir -p /app/wiki

ENV PYTHONUNBUFFERED=1
ENV WIKI_DIR=/app/wiki

# sage-core runs the ingest consumer loop + risk monitor as a long-lived process
CMD ["python", "-m", "knowledge.sage_core"]
