import logging
import os
import hmac
import hashlib
import json
from flask import Flask, request, jsonify, abort

try:
    import requests  # slack notification
except ImportError:  # optional; you can also vendor something else or skip Slack
    requests = None

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")  # must match the SECRET set in `eas webhook:create`
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")  # paste your Slack URL here or export it

app = Flask(__name__)
logger = logging.getLogger(__name__)

def verify_expo_signature(raw_body: bytes, expo_sig: str | None) -> bool:
    """
    Expo's sample uses sha1 and the `expo-signature` header.
    We compute: sha1=<hex>
    """
    if not WEBHOOK_SECRET:  # allow running locally without a secret
        return True
    if not expo_sig:
        return False
    mac = hmac.new(WEBHOOK_SECRET.encode("utf-8"), raw_body, hashlib.sha1)
    expected = "sha1=" + mac.hexdigest()
    return hmac.compare_digest(expected, expo_sig)

def notify_slack(payload: dict) -> None:
    if not SLACK_WEBHOOK_URL:
        logger.warning("SLACK_WEBHOOK_URL not set; skipping Slack notify")
        return
    if requests is None:
        logger.warning("`requests` not installed; skipping Slack notify")
        return

    status = payload.get("status")
    account = payload.get("accountName")
    project = payload.get("projectName")
    platform = payload.get("platform")
    url = payload.get("buildDetailsPageUrl")
    error = (payload.get("error") or {}).get("message")

    text = f"EAS build *{status}* for `{account}/{project}` on *{platform}*"
    if url:
        text += f"\n{url}"
    if error:
        text += f"\nError: `{error}`"

    try:
        resp = requests.post(
            SLACK_WEBHOOK_URL,
            headers={"Content-Type": "application/json"},
            data=json.dumps({"text": text}),
            timeout=5,
        )
        logger.info("Slack response %s %s", resp.status_code, resp.text)
    except Exception:
        logger.exception("Failed to send Slack notification")

@app.get("/health")
def health():
    return jsonify(status="ok")


@app.post("/webhook")
def webhook():
    raw = request.get_data()  # IMPORTANT: use raw bytes for HMAC
    expo_sig = request.headers.get("expo-signature")  # case-insensitive

    if not verify_expo_signature(raw, expo_sig):
        abort(401, description="Signatures didn't match!")

    # Safe to parse now
    payload = request.get_json(silent=True) or {}

    # Do your thing
    notify_slack(payload)

    return jsonify(ok=True)


if __name__ == "__main__":
    # For local dev; use gunicorn/uwsgi/etc. in production.
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "3000")))
