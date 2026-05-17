# cloud/telegram_api.py
import requests
from cal.config import is_local, get_env_var
from cal.secrets import get_secret
from cal.redis_store import set_key
import time


def send_message(chat_id, text, context=None, target_url=None):
    token = get_secret("TELEGRAM_BOT_TOKEN")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    response = requests.post(url, data={"chat_id": chat_id, "text": text})
    result = response.json()

    if context and target_url:
        # Store context in Redis so reply handler can route correctly
        redis_key = f"context:{chat_id}"
        set_key(redis_key, {
            "expected_context": context,
            "target_url": target_url,
            "timestamp": int(time.time())
        }, ex=300)  # Optional TTL of 5 mins

    return result

