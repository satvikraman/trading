"""
Live Telegram round-trip smoke test (no Selenium).

Prerequisites (.env):
  TELEGRAM_BOT_TOKEN=...
  TELEGRAM_CHAT_ID=...

Run from repo root:
  python src/common/test/telegram_live_smoke.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from telegram_client import TelegramClient


def run_live_smoke():
    client = TelegramClient()
    client.drain_updates()
    client.wait_for_yes(
        'Trading bot smoke test. Reply GO within 60s.',
        timeout=60,
        remind_every_sec=None,
    )
    otp = client.wait_for_otp(
        'Reply with any 6-digit number (e.g. 123456).',
        timeout=60,
        remind_every_sec=None,
    )
    if not otp.isdigit() or not (4 <= len(otp) <= 8):
        raise AssertionError(f'Expected OTP digits, got: {otp!r}')
    client.notify('Smoke test OK.')

    offset_after = client.last_update_id
    client2 = TelegramClient()
    if client2.last_update_id < offset_after:
        raise AssertionError('Offset did not persist across client instances')


def test_live_telegram_round_trip():
    """Pytest entry (skipped unless TELEGRAM_LIVE_TEST=1)."""
    import pytest
    if not os.getenv('TELEGRAM_LIVE_TEST'):
        pytest.skip('Set TELEGRAM_LIVE_TEST=1 to run live Telegram smoke test')
    run_live_smoke()


if __name__ == '__main__':
    run_live_smoke()
    print('Live Telegram smoke test passed.')
