#!/usr/bin/env python3
"""Print your Telegram chat_id after you message @sraman_trading_bot once."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src', 'common'))

from dotenv import load_dotenv
import requests

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
if not token:
    print('Set TELEGRAM_BOT_TOKEN in .env first.')
    sys.exit(1)

url = f'https://api.telegram.org/bot{token}/getUpdates'
resp = requests.get(url, timeout=30)
if resp.status_code == 409:
    print('Detected webhook conflict. Removing existing webhook and retrying...')
    delete_url = f'https://api.telegram.org/bot{token}/deleteWebhook?drop_pending_updates=true'
    delete_resp = requests.get(delete_url, timeout=30)
    if not delete_resp.ok or not delete_resp.json().get('ok'):
        print('Failed to delete webhook:', delete_resp.text)
        resp.raise_for_status()
    resp = requests.get(url, timeout=30)

resp.raise_for_status()
data = resp.json()
if not data.get('ok'):
    print(data)
    sys.exit(1)

ids = []
for u in data.get('result', []):
    msg = u.get('message') or u.get('edited_message')
    if not msg:
        continue
    chat = msg.get('chat', {})
    cid = chat.get('id')
    if cid is not None:
        ids.append((cid, chat.get('first_name', ''), chat.get('username', '')))

if not ids:
    print('No messages yet. Open Telegram, message @sraman_trading_bot (e.g. "hi"), then run this again.')
    sys.exit(1)

seen = set()
for cid, name, username in ids:
    if cid in seen:
        continue
    seen.add(cid)
    print(f'TELEGRAM_CHAT_ID={cid}  # {name} @{username}'.strip())
