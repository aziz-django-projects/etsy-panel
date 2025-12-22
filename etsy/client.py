import httpx
from django.conf import settings

API_BASE = "https://api.etsy.com/v3/application"

class EtsyClient:
    def __init__(self, access_token: str):
        self.access_token = access_token
    
    def _headers(self):
        # Etsy v3: Authorization Bearer + x-api-key kullanılır
        return {
            "Authorization": f"Bearer {self.access_token}",
            "x-api-key": f"{settings.ETSY_CLIENT_ID}:{settings.ETSY_SHARED_SECRET}",
        }


    def get_shop_id_for_me(self):
        # “me” üzerinden shop bulma: ileride sağlamlaştırırız
        url = f"{API_BASE}/shops?shop_name="  # placeholder: shop_id’yi biz DB’ye ekleyeceğiz
        raise NotImplementedError

    def get_active_listings(self, shop_id: int, limit: int = 50, offset: int = 0):
        url = f"{API_BASE}/shops/{shop_id}/listings/active"
        params = {"limit": limit, "offset": offset}
        with httpx.Client(timeout=20) as client:
            r = client.get(url, headers=self._headers(), params=params)
            r.raise_for_status()
            return r.json()
            
    def get_user_shops(self, user_id: int):
        url = f"{API_BASE}/users/{user_id}/shops"
        with httpx.Client(timeout=20) as client:
            r = client.get(url, headers=self._headers())
            r.raise_for_status()
            return r.json()

    def get_listing_images(self, listing_id: int):
        url = f"{API_BASE}/listings/{listing_id}/images"
        with httpx.Client(timeout=20) as client:
            r = client.get(url, headers=self._headers())
            r.raise_for_status()
            return r.json()

    def get_shop_receipts(self, shop_id: int, limit: int = 50, offset: int = 0, min_created: int | None = None):
        url = f"{API_BASE}/shops/{shop_id}/receipts"
        params = {"limit": limit, "offset": offset}
        if min_created is not None:
            params["min_created"] = min_created
        with httpx.Client(timeout=20) as client:
            r = client.get(url, headers=self._headers(), params=params)
            r.raise_for_status()
            return r.json()
