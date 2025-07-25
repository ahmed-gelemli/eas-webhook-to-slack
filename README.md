# eas-webhook-to-slack

A lightweight Flask service that receives Expo EAS build webhooks, verifies HMAC signatures, and forwards build status updates to Slack.

## Prerequisites

- Python 3.8+
- Docker & Docker Compose (optional)

## Configuration

1. Copy `.env.example` → `.env`
2. Fill in:

```ini
WEBHOOK_SECRET=your_expo_secret_here
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/…
PORT=3000
````

## Run Locally

```bash
# install dependencies
pip install -r requirements.txt

# load env and start server
export $(cat .env | xargs)
flask --app src/app.py run --port "${PORT:-3000}"
```

## Docker

Build and launch with Compose:

```bash
docker-compose up --build
```
Service will listen on `http://localhost:3000` by default.

## License

Distributed under the MIT License. See [LICENSE](LICENSE) for details.
