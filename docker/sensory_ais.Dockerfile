FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir pydantic redis websockets h3

COPY contracts/    contracts/
COPY knowledge/    knowledge/
COPY sensory_agent/ sensory_agent/

ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "sensory_agent.runner", "ais"]
