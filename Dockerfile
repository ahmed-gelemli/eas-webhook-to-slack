FROM python:3.12-slim

# System deps (curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# Capture version info from git during build (works with Coolify, GitHub Actions, etc.)
# Values are sanitized to prevent shell injection when .build_env is sourced
COPY .git .git
RUN COMMIT_SHA=$(git rev-parse HEAD 2>/dev/null | tr -dc '0-9a-f' | head -c 40) && \
    COMMIT_SHA=${COMMIT_SHA:-unknown} && \
    GIT_BRANCH=$(git branch --show-current 2>/dev/null | tr -dc 'a-zA-Z0-9/_.-' | head -c 128) && \
    GIT_BRANCH=${GIT_BRANCH:-unknown} && \
    BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ") && \
    printf "COMMIT_SHA=%s\nGIT_BRANCH=%s\nAPP_VERSION=%s\nBUILD_DATE=%s\n" \
        "$COMMIT_SHA" "$GIT_BRANCH" "$COMMIT_SHA" "$BUILD_DATE" > /app/.build_env && \
    rm -rf .git
RUN useradd -u 10001 -m worker
RUN chown worker:worker /app/.build_env
USER worker

# Load build env at startup, then run gunicorn
CMD sh -c 'set -a && . /app/.build_env 2>/dev/null; set +a; exec gunicorn -w 2 -b "0.0.0.0:${PORT:-3000}" app:app'