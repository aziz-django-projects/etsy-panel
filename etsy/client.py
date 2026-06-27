import httpx
from django.conf import settings
from django.utils import timezone

API_BASE = "https://api.etsy.com/v3/application"
TOKEN_URL = "https://api.etsy.com/v3/public/oauth/token"
REFRESH_SAFETY_SECONDS = 300


class EtsyAuthError(RuntimeError):
    pass


class EtsyClient:
    def __init__(self, account):
        self.account = account
        self.access_token = account.access_token

    def _headers(self):
        # Etsy v3: Authorization Bearer + x-api-key kullanÄ±lÄ±r
        return {
            "Authorization": f"Bearer {self.access_token}",
            "x-api-key": f"{settings.ETSY_CLIENT_ID}:{settings.ETSY_SHARED_SECRET}",
        }

    def _should_refresh(self):
        if not self.account.refresh_token or not self.account.expires_at:
            return False
        refresh_at = self.account.expires_at - timezone.timedelta(
            seconds=REFRESH_SAFETY_SECONDS
        )
        return timezone.now() >= refresh_at

    def _raise_reconnect_required(self, detail=None):
        message = "Etsy oturumu suresi dolmus. Etsy hesabini yeniden baglayin."
        if detail:
            message = f"{message} ({detail})"
        raise EtsyAuthError(message)

    def _refresh_access_token(self):
        if not self.account.refresh_token:
            self._raise_reconnect_required("refresh token missing")
        data = {
            "grant_type": "refresh_token",
            "client_id": settings.ETSY_CLIENT_ID,
            "refresh_token": self.account.refresh_token,
        }
        with httpx.Client(timeout=20) as client:
            resp = client.post(TOKEN_URL, data=data)
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as exc:
                detail = None
                try:
                    payload = resp.json()
                except ValueError:
                    payload = {}
                error = payload.get("error")
                description = payload.get("error_description")
                if error == "invalid_grant":
                    detail = description or error
                    self._raise_reconnect_required(detail)
                raise exc
            payload = resp.json()

        self.access_token = payload["access_token"]
        self.account.access_token = self.access_token
        new_refresh = payload.get("refresh_token")
        if new_refresh:
            self.account.refresh_token = new_refresh
        expires_in = int(payload.get("expires_in", 3600))
        self.account.expires_at = timezone.now() + timezone.timedelta(seconds=expires_in)
        self.account.save(update_fields=["access_token", "refresh_token", "expires_at"])
        return True

    def _ensure_access_token(self):
        if self.account.expires_at and timezone.now() >= self.account.expires_at:
            if not self.account.refresh_token:
                self._raise_reconnect_required("refresh token missing")
        if self._should_refresh():
            self._refresh_access_token()

    def _get_json(self, url, params=None):
        self._ensure_access_token()
        with httpx.Client(timeout=20) as client:
            resp = client.get(url, headers=self._headers(), params=params)
            if resp.status_code == 401:
                refreshed = self._refresh_access_token()
                if refreshed:
                    resp = client.get(url, headers=self._headers(), params=params)
            resp.raise_for_status()
            return resp.json()

    def get_shop_id_for_me(self):
        # â€œmeâ€ üzerinden shop bulma: ileride saÄŸlamlaÅŸtÄ±rÄ±rÄ±z
        url = f"{API_BASE}/shops?shop_name="  # placeholder: shop_idâ€™yi biz DBâ€™ye ekleyeceÄŸiz
        raise NotImplementedError

    def get_active_listings(self, shop_id: int, limit: int = 50, offset: int = 0):
        url = f"{API_BASE}/shops/{shop_id}/listings/active"
        params = {"limit": limit, "offset": offset}
        return self._get_json(url, params=params)

    def get_user_shops(self, user_id: int):
        url = f"{API_BASE}/users/{user_id}/shops"
        return self._get_json(url)

    def get_listing_images(self, listing_id: int):
        url = f"{API_BASE}/listings/{listing_id}/images"
        return self._get_json(url)

    def get_listing_inventory(self, listing_id: int):
        url = f"{API_BASE}/listings/{listing_id}/inventory"
        return self._get_json(url)

    def get_shop_receipts(
        self,
        shop_id: int,
        limit: int = 50,
        offset: int = 0,
        min_created: int | None = None,
    ):
        url = f"{API_BASE}/shops/{shop_id}/receipts"
        params = {"limit": limit, "offset": offset}
        if min_created is not None:
            params["min_created"] = min_created
        return self._get_json(url, params=params)
