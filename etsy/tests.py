from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from .client import EtsyClient, EtsyRateLimitError


class EtsyRateLimitTests(SimpleTestCase):
    @patch("etsy.client.time.sleep")
    @patch("etsy.client.httpx.Client")
    def test_short_retry_after_retries_once(self, http_client_class, sleep):
        account = SimpleNamespace(access_token="token", refresh_token="", expires_at=None)
        client = EtsyClient(account)
        rate_limited = Mock(status_code=429, headers={"retry-after": "1"})
        successful = Mock(status_code=200)
        successful.json.return_value = {"results": []}
        http_client_class.return_value.__enter__.return_value.get.side_effect = [
            rate_limited, successful,
        ]

        self.assertEqual(client._get_json("https://example.com"), {"results": []})
        sleep.assert_called_once_with(1.0)

    @patch("etsy.client.time.sleep")
    @patch("etsy.client.httpx.Client")
    def test_long_retry_after_stops_without_retrying(self, http_client_class, sleep):
        account = SimpleNamespace(access_token="token", refresh_token="", expires_at=None)
        client = EtsyClient(account)
        http_get = http_client_class.return_value.__enter__.return_value.get
        http_get.return_value = Mock(status_code=429, headers={"retry-after": "3600"})

        with self.assertRaises(EtsyRateLimitError):
            client._get_json("https://example.com")

        http_get.assert_called_once()
        sleep.assert_not_called()
