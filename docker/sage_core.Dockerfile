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
# The monitor's autonomous response pipeline (orchestration/graph.py) imports these
# three System 2/3/4 agent packages IN-PROCESS, so sage-core must ship them — not
# just the standalone agent containers. Without these the pipeline dies with
# "No module named 'scenario_agent'" the moment a risk crosses the action band.
COPY scenario_agent/       scenario_agent/
COPY alt_procurement_agent/ alt_procurement_agent/
COPY reserve_optim_agent/  reserve_optim_agent/
COPY scripts/       scripts/

RUN mkdir -p /app/wiki

ENV PYTHONUNBUFFERED=1
ENV WIKI_DIR=/app/wiki

# sage-core runs the ingest consumer loop + risk monitor as a long-lived process
CMD ["python", "-m", "knowledge.sage_core"]
