FROM python:3.11-slim AS base

LABEL org.opencontainers.image.version="2.3.0"
LABEL org.opencontainers.image.source="https://github.com/DXN1-termux/BUGHUNTER-AI"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl git nmap \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY slm/ ./slm/
COPY prompts/ ./prompts/
COPY eval/ ./eval/

RUN pip install --no-cache-dir -e .

ENV SLM_HOME=/data
VOLUME /data

RUN slm init 2>/dev/null || true

ENTRYPOINT ["slm"]
CMD ["--help"]
