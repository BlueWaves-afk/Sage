FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir pydantic redis numpy scipy scikit-learn

# PyTorch CPU build for environments without GPU (swap to +cu118 on GPU host)
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY contracts/      contracts/
COPY knowledge/      knowledge/
COPY scenario_agent/ scenario_agent/

ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "scenario_agent.runner"]
