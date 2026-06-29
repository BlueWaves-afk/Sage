FROM python:3.11-slim
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir pydantic redis numpy scipy

COPY contracts/           contracts/
COPY knowledge/           knowledge/
COPY reserve_optim_agent/ reserve_optim_agent/

ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "reserve_optim_agent.runner"]
