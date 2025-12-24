import httpx
from django.conf import settings
from django.core.cache import cache

TOKEN_CACHE_KEY = "shipentegra:access_token"
TOKEN_TTL_BUFFER_SECONDS = 60
TOKEN_TTL_FALLBACK_SECONDS = 30 * 60


def _parse_token_validity(value):
    if value is None:
        return TOKEN_TTL_FALLBACK_SECONDS
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if text.isdigit():
            return int(text)
        parts = text.split(":")
        if all(part.isdigit() for part in parts):
            values = [int(part) for part in parts]
            if len(values) == 3:
                hours, minutes, seconds = values
                return hours * 3600 + minutes * 60 + seconds
            if len(values) == 2:
                minutes, seconds = values
                return minutes * 60 + seconds
    return TOKEN_TTL_FALLBACK_SECONDS


class ShipentegraClient:
    def __init__(self):
        self.base_url = settings.SHIPENTEGRA_BASE_URL.rstrip("/")
        self.client_id = settings.SHIPENTEGRA_CLIENT_ID
        self.client_secret = settings.SHIPENTEGRA_CLIENT_SECRET

    def _get_access_token(self):
        cached = cache.get(TOKEN_CACHE_KEY)
        if cached:
            return cached

        if not self.client_id or not self.client_secret:
            return None

        url = f"{self.base_url}/auth/token"
        payload = {
            "clientId": self.client_id,
            "clientSecret": self.client_secret,
        }
        with httpx.Client(timeout=20) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

        token = (data.get("data") or {}).get("accessToken")
        validity = (data.get("data") or {}).get("accessTokenValidity")
        ttl = _parse_token_validity(validity)
        if token:
            cache.set(
                TOKEN_CACHE_KEY,
                token,
                max(ttl - TOKEN_TTL_BUFFER_SECONDS, 60),
            )
        return token

    def get_shipment_activities(self, tracking_number):
        token = self._get_access_token()
        if not token:
            return None

        url = f"{self.base_url}/logistics/shipments/activities"
        headers = {"Authorization": f"Bearer {token}"}
        params = {"trackingNumber": tracking_number}
        with httpx.Client(timeout=20) as client:
            response = client.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()
