FROM python:3.12-slim

# System deps (curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# Build arguments for version information
ARG VERSION=unknown
ARG COMMIT_SHA=unknown
ARG BUILD_DATE=unknown
ARG GIT_BRANCH=unknown

ENV APP_VERSION=$VERSION
ENV COMMIT_SHA=$COMMIT_SHA
ENV BUILD_DATE=$BUILD_DATE
ENV GIT_BRANCH=$GIT_BRANCH

# Non-root (optional)
RUN useradd -u 10001 -m worker
USER worker

# Gunicorn with 2 workers, 1 thread each—tweak if needed
CMD gunicorn -w 2 -b "0.0.0.0:${PORT:-3000}" app:app