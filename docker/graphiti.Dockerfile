# graphiti container — runs the KB bootstrap only then stays alive for health checks
# In SAGE the actual graphiti calls happen inside sage-core and api-gateway;
# this container exists purely to pre-warm FalkorDB indices on startup.
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc g++ libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir "graphiti-core[falkordb]" pydantic boto3

COPY contracts/  contracts/
COPY knowledge/  knowledge/

ENV PYTHONUNBUFFERED=1

# Run bootstrap once, then exit (sage-core owns the long-lived connection)
CMD ["python", "-c", "
import asyncio
from knowledge.connection import init
asyncio.run(init())
print('Bootstrap complete.')
"]
