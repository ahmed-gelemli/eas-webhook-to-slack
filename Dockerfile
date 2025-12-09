FROM python:3.12-slim

# System deps (curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# Non-root (optional)
RUN useradd -u 10001 -m worker
USER worker

ENV PORT=3000
# Gunicorn with 2 workers, 1 thread each—tweak if needed
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:3000", "app:app"]