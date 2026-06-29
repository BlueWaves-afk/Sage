FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ libffi-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir \
    "graphiti-core[falkordb]" pydantic boto3 redis \
    fastapi "uvicorn[standard]" langgraph langchain-core \
    numpy scikit-learn shap

COPY contracts/        contracts/
COPY knowledge/        knowledge/
COPY orchestration/    orchestration/
COPY sensory_agent/    sensory_agent/
COPY visualizer_agent/ visualizer_agent/
COPY demo_cache/       demo_cache/

ENV PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["uvicorn", "visualizer_agent.api_gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
