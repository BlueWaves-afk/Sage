FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir pydantic redis numpy scikit-learn ortools

COPY contracts/             contracts/
COPY knowledge/             knowledge/
COPY alt_procurement_agent/ alt_procurement_agent/

ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "alt_procurement_agent.runner"]
