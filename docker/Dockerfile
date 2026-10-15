# flaky-hunt and its self-tests, in a clean UTC Python.
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends make && rm -rf /var/lib/apt/lists/*
WORKDIR /src
COPY pyproject.toml README.md ./
COPY src src
RUN pip install --no-cache-dir -e '.[dev]'
COPY . .
