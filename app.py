import logging
import os
import hmac
import hashlib
import json
import uuid
from functools import lru_cache
from flask import Flask, request, jsonify, abort
from werkzeug.exceptions import HTTPException

try:
    import requests  # slack notification
except ImportError:  # optional; you can also vendor something else or skip Slack
    requests = None

@lru_cache(maxsize=1)
def _secrets_json() -> dict:
    raw = os.getenv("APP_SECRETS_JSON", "")
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        # Don't crash local/dev if someone sets it wrong; just ignore it.
        return {}


def getenv(name: str, default: str = "") -> str:
    # Local/dev: let developers keep using plain env vars
    v = os.getenv(name)
    if v is not None:
        return v

    # Production: values come via APP_SECRETS_JSON
    return str(_secrets_json().get(name, default))


WEBHOOK_SECRET = getenv("WEBHOOK_SECRET", "")  # must match the SECRET set in `eas webhook:create`
SLACK_WEBHOOK_URL = getenv("SLACK_WEBHOOK_URL", "")  # paste your Slack URL here or export it

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
# Set maximum content length to prevent DoS (10MB)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024


@app.errorhandler(413)
def request_entity_too_large(error):
    logger.warning("Request entity too large")
    return jsonify(error="Request entity too large"), 413


@app.errorhandler(400)
def bad_request(error):
    return jsonify(error=error.description or "Bad request"), 400


@app.errorhandler(500)
def internal_error(error):
    logger.exception("Internal server error")
    return jsonify(error="Internal server error"), 500

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
    checks = {
        "status": "ok",
        "version": os.getenv("APP_VERSION", "unknown"),
        "slack_configured": bool(SLACK_WEBHOOK_URL),
        "requests_available": requests is not None,
    }
    status_code = 200 # if checks["slack_configured"] and checks["requests_available"] else 503
    return jsonify(checks), status_code


@app.get("/version")
def version():
    return jsonify({
        "version": os.getenv("APP_VERSION", "unknown"),
        "commit_sha": os.getenv("COMMIT_SHA", "unknown"),
        "build_date": os.getenv("BUILD_DATE", "unknown"),
        "branch": os.getenv("GIT_BRANCH", "unknown"),
    })


@app.post("/webhook")
def webhook():
    request_id = str(uuid.uuid4())
    logger.info("Webhook request received", extra={"request_id": request_id})

    try:
        raw = request.get_data()  # IMPORTANT: use raw bytes for HMAC
        expo_sig = request.headers.get("expo-signature")  # case-insensitive

        if not verify_expo_signature(raw, expo_sig):
            logger.warning("Signature verification failed", extra={"request_id": request_id})
            abort(401, description="Signatures didn't match!")

        # Parse JSON with proper error handling
        try:
            payload = request.get_json(force=True)
            if payload is None:
                logger.warning("Empty or invalid JSON payload", extra={"request_id": request_id})
                abort(400, description="Invalid JSON payload")
        except Exception as e:
            logger.error("JSON parsing failed", extra={"request_id": request_id, "error": str(e)})
            abort(400, description="Invalid JSON payload")

        # Validate required fields
        if not isinstance(payload, dict):
            logger.warning("Payload is not a dictionary", extra={"request_id": request_id})
            abort(400, description="Payload must be a JSON object")

        notify_slack(payload)

        logger.info("Webhook processed successfully", extra={"request_id": request_id})
        return jsonify(ok=True)

    except HTTPException:
        # Re-raise HTTP exceptions (from abort()) so Flask handles them properly
        raise
    except Exception as e:
        logger.exception("Unexpected error processing webhook", extra={"request_id": request_id})
        abort(500, description="Internal server error")


if __name__ == "__main__":
    port = int(os.getenv("PORT", "3000"))
    app.run(host="0.0.0.0", port=port)
