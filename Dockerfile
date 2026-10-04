# syntax=docker/dockerfile:1.7

FROM python:3.13-slim-bookworm AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN useradd --create-home --uid 1000 botuser && mkdir -p /app/var && chown botuser /app/var

COPY pyproject.toml README.md ./
COPY bot ./bot

RUN pip install --no-cache-dir .

USER botuser

CMD ["python", "-m", "bot"]

FROM base AS tests
USER root
RUN pip install --no-cache-dir ".[dev]"
COPY tests ./tests
USER botuser
CMD ["python", "-m", "pytest", "-q"]

# A plain docker build produces the runnable bot, not the test runner.
FROM base AS runtime
