import json
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from telegram_client import TelegramClient, extract_otp


class TestExtractOtp(unittest.TestCase):
    def test_extracts_six_digits(self):
        self.assertEqual(extract_otp('My OTP is 123456'), '123456')

    def test_none_when_missing(self):
        self.assertIsNone(extract_otp('hello'))


class TestTelegramClientPersistence(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.state_path = os.path.join(self.tmpdir, 'telegram_state.json')
        self.lock_path = os.path.join(self.tmpdir, 'telegram_state.lock')

    @patch.dict(os.environ, {'TELEGRAM_BOT_TOKEN': 'test-token', 'TELEGRAM_CHAT_ID': '999'})
    @patch('telegram_client.requests.get')
    @patch('telegram_client.requests.post')
    def test_offset_persisted_after_updates(self, mock_post, mock_get):
        mock_post.return_value = MagicMock(ok=True, raise_for_status=MagicMock(), json=lambda: {'ok': True})

        poll_results = [
            {'ok': True, 'result': [
                {'update_id': 100, 'message': {'chat': {'id': 999}, 'text': 'noise'}},
                {'update_id': 101, 'message': {'chat': {'id': 999}, 'text': '123456'}},
            ]},
            {'ok': True, 'result': []},
        ]

        def get_side_effect(url, *args, **kwargs):
            resp = MagicMock(ok=True, raise_for_status=MagicMock())
            if 'deleteWebhook' in url:
                resp.json.return_value = {'ok': True}
                return resp
            body = poll_results.pop(0) if poll_results else {'ok': True, 'result': []}
            resp.json.return_value = body
            return resp

        mock_get.side_effect = get_side_effect

        client = TelegramClient(state_path=self.state_path, lock_path=self.lock_path)
        client.drain_updates()

        with open(self.state_path, encoding='utf-8') as f:
            state = json.load(f)
        self.assertEqual(state['last_update_id'], 101)

        client2 = TelegramClient(state_path=self.state_path, lock_path=self.lock_path)
        self.assertEqual(client2.last_update_id, 101)

    @patch.dict(os.environ, {'TELEGRAM_BOT_TOKEN': 'test-token', 'TELEGRAM_CHAT_ID': '999'})
    @patch('telegram_client.requests.get')
    @patch('telegram_client.requests.post')
    def test_wait_for_otp_returns_first_match(self, mock_post, mock_get):
        mock_post.return_value = MagicMock(ok=True, raise_for_status=MagicMock(), json=lambda: {'ok': True})

        getupdate_calls = [0]

        def get_side_effect(url, *args, **kwargs):
            resp = MagicMock(ok=True, raise_for_status=MagicMock())
            if 'deleteWebhook' in url:
                resp.json.return_value = {'ok': True}
                return resp
            getupdate_calls[0] += 1
            if getupdate_calls[0] == 1:
                resp.json.return_value = {'ok': True, 'result': []}
            else:
                resp.json.return_value = {'ok': True, 'result': [
                    {'update_id': 200, 'message': {'chat': {'id': 999}, 'text': '654321'}},
                ]}
            return resp

        mock_get.side_effect = get_side_effect

        client = TelegramClient(state_path=self.state_path, lock_path=self.lock_path)
        otp = client.wait_for_otp('Enter OTP', timeout=5)
        self.assertEqual(otp, '654321')

    @patch.dict(os.environ, {'TELEGRAM_BOT_TOKEN': 'test-token', 'TELEGRAM_CHAT_ID': '999'})
    @patch('telegram_client.requests.get')
    @patch('telegram_client.requests.post')
    def test_wait_for_yes_accepts_go(self, mock_post, mock_get):
        mock_post.return_value = MagicMock(ok=True, raise_for_status=MagicMock(), json=lambda: {'ok': True})
        getupdate_calls = [0]

        def get_side_effect(url, *args, **kwargs):
            resp = MagicMock(ok=True, raise_for_status=MagicMock())
            if 'deleteWebhook' in url:
                resp.json.return_value = {'ok': True}
                return resp
            getupdate_calls[0] += 1
            if getupdate_calls[0] == 1:
                resp.json.return_value = {'ok': True, 'result': []}
            else:
                resp.json.return_value = {'ok': True, 'result': [
                    {'update_id': 300, 'message': {'chat': {'id': 999}, 'text': 'GO'}},
                ]}
            return resp

        mock_get.side_effect = get_side_effect

        client = TelegramClient(state_path=self.state_path, lock_path=self.lock_path)
        self.assertTrue(client.wait_for_yes('Reply GO', timeout=5))


if __name__ == '__main__':
    unittest.main()
