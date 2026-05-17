# bot/telegram_handler.py
from cal.redis_store import get_key, delete_key
import requests
import time

def safe_post(url, json_data, retries=3, backoff=2):
    for attempt in range(retries):
        try:
            response = requests.post(url, json=json_data, timeout=5)
            if response.status_code == 200:
                return True
        except requests.exceptions.RequestException as e:
            print(f"[Retry] Attempt {attempt+1} failed: {e}")
            time.sleep(backoff * (attempt + 1))
    return False


def handle_telegram_webhook(payload):
    message = payload.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    user_text = message.get("text", "").strip()

    # Lookup expected context
    context = get_key(f"context:{chat_id}")
    if context is None:
        return {"status": "no_context", "message": "No backend session in progress"}

    # Forward user_text to microservice
    success = safe_post(context["target_url"], {
        "source": "telegram",
        "chat_id": chat_id,
        "message": user_text,
        "timestamp": int(time.time())
    })
    if success:
        delete_key(f"context:{chat_id}")
        return {"status": "success"}
    else:
        # Optional: log or persist the message in Redis to retry later
        return {"status": "failed", "message": "Backend not reachable"}


def extract_otp(text):
    import re
    match = re.search(r"\b\d{4,8}\b", text)
    return match.group(0) if match else None
