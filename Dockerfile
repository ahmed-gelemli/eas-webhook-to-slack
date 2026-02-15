FROM python:3.12-slim

# System deps (curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# Build args for version info (Coolify: add COMMIT_SHA=$SOURCE_COMMIT, GIT_BRANCH=$COOLIFY_BRANCH as build variables)
ARG COMMIT_SHA=unknown
ARG GIT_BRANCH=unknown
ARG BUILD_DATE=unknown

ENV APP_VERSION=$COMMIT_SHA
ENV COMMIT_SHA=$COMMIT_SHA
ENV BUILD_DATE=$BUILD_DATE
ENV GIT_BRANCH=$GIT_BRANCH

RUN useradd -u 10001 -m worker
USER worker

CMD ["sh", "-c", "exec gunicorn -w 2 -b \"0.0.0.0:${PORT:-3000}\" app:app"]