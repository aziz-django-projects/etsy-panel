from etsy.client import EtsyClient
from etsy.models import EtsyAccount
from .models import Listing

def sync_active_listings(user):
    account = EtsyAccount.objects.get(user=user)
    client = EtsyClient(account.access_token)

    # Shop_id yoksa önce shop’ları çek
    if not account.shop_id:
        if not account.etsy_user_id:
            raise RuntimeError("etsy_user_id is missing. Please re-connect Etsy.")  # (aynı)

        shops_payload = client.get_user_shops(account.etsy_user_id)

        # CHANGED: Etsy bazı çağrılarda {"results":[...]} yerine direkt tek shop dict döndürebiliyor.
        # Bu yüzden payload tipine göre parse ediyoruz.
        if isinstance(shops_payload, dict):
            # CHANGED: Eğer "results" varsa liste gibi ele al, yoksa direkt dict'i tek shop kabul et
            results = shops_payload.get("results")
            if results is None:
                results = [shops_payload]
        elif isinstance(shops_payload, list):
            # CHANGED: Bazı durumlarda direkt liste dönebilir
            results = shops_payload
        else:
            # CHANGED: Beklenmeyen payload tipi
            results = []

        if not results:
            raise RuntimeError("No shop found for this Etsy account.")

        shop = results[0]  # şimdilik ilk shop
        account.shop_id = shop.get("shop_id")           # CHANGED: artık payload'da kesin var
        account.shop_name = shop.get("shop_name", "")   # CHANGED: artık payload'da kesin var
        account.save()



    # Active listings çek (sayfalı)
    offset = 0
    limit = 50
    total = 0

    while True:
        payload = client.get_active_listings(shop_id=account.shop_id, limit=limit, offset=offset)
        items = payload.get("results", [])
        if not items:
            break

        for it in items:
            Listing.objects.update_or_create(
                etsy_listing_id=it["listing_id"],
                defaults={
                    "owner": user,
                    "title": it.get("title", ""),
                    "state": it.get("state", ""),
                    "url": it.get("url", ""),
                    "quantity": it.get("quantity"),
                    "price_amount": (it.get("price") or {}).get("amount"),
                    "price_currency": (it.get("price") or {}).get("currency_code", ""),
                },
            )
            total += 1

        offset += limit

    return total
