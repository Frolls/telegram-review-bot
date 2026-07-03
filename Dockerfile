# syntax=docker/dockerfile:1.7

FROM python:3.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN useradd --create-home --uid 1000 botuser

COPY pyproject.toml README.md ./
COPY bot ./bot

RUN pip install --no-cache-dir .

USER botuser

CMD ["python", "-m", "bot"]
