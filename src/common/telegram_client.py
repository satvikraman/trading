"""
Telegram Bot API client for login OTP / prompts (long polling).

Setup (.env):
  TELEGRAM_BOT_TOKEN=...   # from @BotFather
  TELEGRAM_CHAT_ID=...     # numeric; message your bot once, then use getUpdates or @userinfobot

State is persisted under ./data/telegram_state.json (last_update_id).
Call delete_webhook on startup so getUpdates works if a webhook was set earlier.

Login waits (wait_for_yes / wait_for_otp / etc.) block until you reply (no hard timeout).
A reminder is sent every LOGIN_REMIND_EVERY_SEC (15 minutes) while waiting.
Pass timeout=... and remind_every_sec=None for bounded tests (e.g. smoke test).
"""

import json
import logging
import os
import re
import time
from contextlib import contextmanager
from typing import Callable, List, Optional, Union

try:
    import dotenv
except ImportError:
    dotenv = None
import requests

DEFAULT_STATE_PATH = './data/telegram_state.json'
DEFAULT_LOCK_PATH = './data/telegram_state.lock'
API_BASE = 'https://api.telegram.org/bot'
POLL_TIMEOUT_SEC = 30
# Login flows: wait until reply; remind every 15 minutes (no hard timeout by default).
LOGIN_REMIND_EVERY_SEC = 900

YES_ALIASES = frozenset({'YES', 'Y', 'GO', 'OK', 'DONE'})
RESEND_ALIASES = frozenset({'RESEND', 'R'})


def extract_otp(text: str) -> Optional[str]:
    if not text:
        return None
    match = re.search(r'\b(\d{4,8})\b', text.strip())
    return match.group(1) if match else None


class TelegramTimeoutError(TimeoutError):
    pass


class TelegramClient:
    def __init__(self, logger=None, state_path=DEFAULT_STATE_PATH, lock_path=DEFAULT_LOCK_PATH):
        self._logger = logger or logging.getLogger(__name__)
        if dotenv is not None:
            dotenv.load_dotenv('./.env', override=False)
        self._token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
        self._chat_id = int(os.environ.get('TELEGRAM_CHAT_ID', '0') or '0')
        self._state_path = state_path
        self._lock_path = lock_path
        self._api = f'{API_BASE}{self._token}'
        self._last_update_id = 0
        self._load_state()
        self.delete_webhook()

    def _require_config(self):
        if not self._token:
            raise ValueError('TELEGRAM_BOT_TOKEN is not set in .env')
        if not self._chat_id:
            raise ValueError('TELEGRAM_CHAT_ID is not set in .env')

    @contextmanager
    def _file_lock(self):
        os.makedirs(os.path.dirname(self._lock_path) or '.', exist_ok=True)
        while True:
            try:
                fd = os.open(self._lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                try:
                    yield
                finally:
                    os.close(fd)
                    try:
                        os.unlink(self._lock_path)
                    except OSError:
                        pass
                break
            except FileExistsError:
                time.sleep(0.05)

    def _read_state_unlocked(self):
        if os.path.isfile(self._state_path):
            try:
                with open(self._state_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self._last_update_id = int(data.get('last_update_id', 0))
            except (json.JSONDecodeError, ValueError, TypeError) as e:
                self._logger.warning('Could not read %s: %s', self._state_path, e)
                self._last_update_id = 0

    def _write_state_unlocked(self):
        os.makedirs(os.path.dirname(self._state_path) or '.', exist_ok=True)
        with open(self._state_path, 'w', encoding='utf-8') as f:
            json.dump({'last_update_id': self._last_update_id}, f)

    def _load_state(self):
        with self._file_lock():
            self._read_state_unlocked()

    def _save_state(self):
        with self._file_lock():
            self._write_state_unlocked()

    @property
    def last_update_id(self) -> int:
        return self._last_update_id

    def delete_webhook(self):
        self._require_config()
        try:
            requests.get(f'{self._api}/deleteWebhook', timeout=15)
        except requests.RequestException as e:
            self._logger.warning('deleteWebhook failed: %s', e)

    def _post(self, method: str, data=None, files=None) -> dict:
        self._require_config()
        url = f'{self._api}/{method}'
        if files:
            resp = requests.post(url, data=data, files=files, timeout=60)
        else:
            resp = requests.post(url, json=data, timeout=60)
        resp.raise_for_status()
        body = resp.json()
        if not body.get('ok'):
            raise RuntimeError(f'Telegram API {method} failed: {body}')
        return body

    def notify(self, text: str) -> dict:
        result = self._post('sendMessage', {
            'chat_id': self._chat_id,
            'text': text,
        })
        return result

    def send_photo(self, photo_path: str, caption: str = '') -> dict:
        with open(photo_path, 'rb') as photo:
            return self._post('sendPhoto', {
                'chat_id': self._chat_id,
                'caption': caption,
            }, files={'photo': photo})

    def _fetch_updates(self, timeout_sec: int = POLL_TIMEOUT_SEC) -> List[dict]:
        with self._file_lock():
            self._read_state_unlocked()
            offset = self._last_update_id + 1
        params = {'offset': offset, 'timeout': timeout_sec}
        resp = requests.get(f'{self._api}/getUpdates', params=params, timeout=timeout_sec + 10)
        resp.raise_for_status()
        body = resp.json()
        if not body.get('ok'):
            raise RuntimeError(f'getUpdates failed: {body}')
        return body.get('result', [])

    def _ack_updates(self, updates: List[dict]):
        if not updates:
            return
        max_id = max(u['update_id'] for u in updates)
        with self._file_lock():
            self._read_state_unlocked()
            if max_id > self._last_update_id:
                self._last_update_id = max_id
                self._write_state_unlocked()

    def drain_updates(self):
        """Acknowledge all pending updates without acting on them."""
        while True:
            updates = self._fetch_updates(timeout_sec=0)
            if not updates:
                break
            self._ack_updates(updates)

    def _message_from_update(self, update: dict) -> Optional[dict]:
        msg = update.get('message') or update.get('edited_message')
        if not msg or 'text' not in msg:
            return None
        chat = msg.get('chat', {})
        if chat.get('id') != self._chat_id:
            return None
        return msg

    def _poll_until(
        self,
        predicate: Callable[[str], Optional[Union[str, bool]]],
        timeout: Optional[float] = None,
        remind_every_sec: Optional[float] = None,
        remind_text: Optional[str] = None,
    ) -> str:
        deadline = None if timeout is None else time.time() + timeout
        last_reminder_at = time.time()
        while deadline is None or time.time() < deadline:
            if (
                remind_every_sec
                and remind_text
                and (time.time() - last_reminder_at) >= remind_every_sec
            ):
                self.notify(remind_text)
                last_reminder_at = time.time()
            updates = self._fetch_updates()
            for update in updates:
                msg = self._message_from_update(update)
                if msg is None:
                    continue
                text = msg.get('text', '').strip()
                result = predicate(text)
                if result is not None and result is not False:
                    self._ack_updates(updates)
                    return str(result) if result is not True else text
            self._ack_updates(updates)
        raise TelegramTimeoutError(f'Timed out after {timeout}s waiting for Telegram reply')

    def wait_for_yes(
        self,
        prompt: str,
        timeout: Optional[float] = None,
        remind_every_sec: Optional[float] = LOGIN_REMIND_EVERY_SEC,
    ):
        self.drain_updates()
        self.notify(prompt)
        remind = f'Still waiting: {prompt}' if remind_every_sec else None
        return self.poll_for_yes(timeout=timeout, remind_every_sec=remind_every_sec, remind_text=remind)

    def poll_for_yes(
        self,
        timeout: Optional[float] = None,
        remind_every_sec: Optional[float] = LOGIN_REMIND_EVERY_SEC,
        remind_text: Optional[str] = None,
    ):
        def pred(text: str):
            if text.upper() in YES_ALIASES:
                return True
            return None

        final_remind = (remind_text or 'Still waiting. Reply GO when ready.') if remind_every_sec else None
        self._poll_until(
            pred,
            timeout=timeout,
            remind_every_sec=remind_every_sec,
            remind_text=final_remind,
        )
        return True

    def wait_for_otp(
        self,
        prompt: str,
        timeout: Optional[float] = None,
        remind_every_sec: Optional[float] = LOGIN_REMIND_EVERY_SEC,
    ) -> str:
        self.drain_updates()
        self.notify(prompt)
        remind = f'Still waiting: {prompt}' if remind_every_sec else None
        return self.poll_for_otp(timeout=timeout, remind_every_sec=remind_every_sec, remind_text=remind)

    def poll_for_otp(
        self,
        timeout: Optional[float] = None,
        remind_every_sec: Optional[float] = LOGIN_REMIND_EVERY_SEC,
        remind_text: Optional[str] = None,
    ) -> str:
        def pred(text: str):
            otp = extract_otp(text)
            return otp

        final_remind = (remind_text or 'Still waiting for OTP reply.') if remind_every_sec else None
        return self._poll_until(
            pred,
            timeout=timeout,
            remind_every_sec=remind_every_sec,
            remind_text=final_remind,
        )

    def wait_for_choice(
        self,
        prompt: str,
        choices: List[str],
        timeout: Optional[float] = None,
        remind_every_sec: Optional[float] = LOGIN_REMIND_EVERY_SEC,
    ) -> str:
        self.drain_updates()
        choices_upper = [c.upper() for c in choices]
        full_prompt = f'{prompt}\nOptions: {", ".join(choices)}'
        self.notify(full_prompt)
        remind = f'Still waiting: {full_prompt}' if remind_every_sec else None

        def pred(text: str):
            upper = text.strip().upper()
            if upper in choices_upper:
                return upper
            return None

        return self._poll_until(
            pred,
            timeout=timeout,
            remind_every_sec=remind_every_sec,
            remind_text=remind,
        )

    def wait_for_resend_or_otp(
        self,
        prompt: str,
        timeout: Optional[float] = None,
        remind_every_sec: Optional[float] = LOGIN_REMIND_EVERY_SEC,
    ) -> str:
        """
        Returns 'RESEND' or a digit OTP string.
        """
        self.drain_updates()
        self.notify(prompt)
        remind = f'Still waiting: {prompt}' if remind_every_sec else None

        def pred(text: str):
            upper = text.strip().upper()
            if upper in RESEND_ALIASES or 'RESEND' in upper:
                return 'RESEND'
            otp = extract_otp(text)
            if otp:
                return otp
            return None

        return self._poll_until(
            pred,
            timeout=timeout,
            remind_every_sec=remind_every_sec,
            remind_text=remind,
        )
