FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        git \
        ripgrep \
        coreutils \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --no-cache-dir \
    build \
    pytest \
    ruff

RUN useradd \
    --create-home \
    --uid 1000 \
    --shell /bin/sh \
    agent

WORKDIR /workspace/repository

USER agent

CMD ["sleep", "infinity"]
