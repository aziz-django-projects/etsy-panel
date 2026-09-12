import logging

from etsy.client import EtsyClient
from etsy.models import EtsyAccount

from .models import Listing, ListingVariation

logger = logging.getLogger(__name__)


def _extract_variation_label(property_values):
    """Varyasyon değerlerini ekranda gösterilecek tek bir etikete dönüştür."""
    labels = []
    for property_value in property_values or []:
        if not isinstance(property_value, dict):
            continue
        values = property_value.get("values") or []
        if isinstance(values, list):
            for value in values:
                if value:
                    labels.append(str(value))
        if labels:
            continue
        value_ids = property_value.get("value_ids") or []
        if isinstance(value_ids, list):
            for value_id in value_ids:
                if value_id is not None:
                    labels.append(str(value_id))
    return " / ".join(labels).strip()


def _extract_value_ids(property_values):
    """Etsy'nin varyasyon değer ID'lerini daha sonra eşleştirmek için topla."""
    value_ids = []
    for property_value in property_values or []:
        if not isinstance(property_value, dict):
            continue
        ids = property_value.get("value_ids") or []
        if isinstance(ids, list):
            for value_id in ids:
                if value_id is not None:
                    value_ids.append(value_id)
    return value_ids


def _sync_listing_variations(listing, products):
    """Bir ilanın varyasyonlarını Etsy envanteriyle eşitle."""
    seen_product_ids = set()

    for product in products:
        product_id = product.get("product_id")
        if not product_id:
            continue

        property_values = product.get("property_values") or []
        seen_product_ids.add(product_id)
        label = _extract_variation_label(property_values)
        if not label:
            continue

        ListingVariation.objects.update_or_create(
            listing=listing,
            etsy_product_id=product_id,
            defaults={
                "label": label,
                "property_values_raw": property_values,
                "value_ids": _extract_value_ids(property_values),
                "is_deleted": bool(product.get("is_deleted")),
                "raw": product,
            },
        )

    # Etsy'den artık gelmeyen veya etiketi boş olan yerel varyasyonları temizle.
    ListingVariation.objects.filter(listing=listing).exclude(
        etsy_product_id__in=seen_product_ids
    ).delete()
    ListingVariation.objects.filter(listing=listing, label="").delete()
    return len(seen_product_ids)


def sync_active_listings(user):
    """Aktif Etsy ilanlarını ve varyasyonlarını yerel kayıtlara aktar.

    Artık aktif olmayan ilanları silmez ve Etsy'deki stok miktarını değiştirmez.
    """
    account = EtsyAccount.objects.get(user=user)
    client = EtsyClient(account)

    # Mağaza ID'si yalnızca eksikse Etsy'den bulunur ve sonraki eşitlemeler için saklanır.
    if not account.shop_id:
        if not account.etsy_user_id:
            raise RuntimeError("etsy_user_id is missing. Please re-connect Etsy.") 

        shops_payload = client.get_user_shops(account.etsy_user_id)

        if isinstance(shops_payload, dict):
            results = shops_payload.get("results")
            if results is None:
                results = [shops_payload]
        elif isinstance(shops_payload, list):
            results = shops_payload
        else:
            results = []

        if not results:
            raise RuntimeError("No shop found for this Etsy account.")

        shop = results[0] 
        account.shop_id = shop.get("shop_id")        
        account.shop_name = shop.get("shop_name", "") 
        account.save()



    # Aktif ilanları Etsy API'sinden 50'şer kayıt halinde çek.
    offset = 0
    limit = 50
    listings_synced = 0
    variation_sync_ok = 0
    variation_sync_failed = 0

    while True:
        payload = client.get_active_listings(shop_id=account.shop_id, limit=limit, offset=offset)
        items = payload.get("results", [])
        if not items:
            break

        # Her ilan için ayrı istek yerine sayfadaki görsel ve envanterleri toplu çek.
        listing_ids = [item["listing_id"] for item in items]
        images_payload = client.get_listings_with_images(listing_ids)
        images_by_id = {
            item["listing_id"]: item.get("images") or []
            for item in images_payload.get("results", [])
        }
        inventory_payload = client.get_listings_inventory_batch(listing_ids)
        inventory_by_id = {
            item["listing_id"]: item.get("inventory")
            for item in inventory_payload.get("results", [])
        }

        for it in items:
            # Görsel gelmezse ilan yine kaydedilir; görsel alanları boş kalır.
            image_url_170x135 = ""
            image_url_75x75 = ""
            image_results = images_by_id.get(it["listing_id"], [])
            if image_results:
                image_url_170x135 = image_results[0].get("url_170x135", "")
                image_url_75x75 = image_results[0].get("url_75x75", "")

            # Etsy listing ID'sine göre mevcut kaydı güncelle veya yeni kayıt oluştur.
            listing, _ = Listing.objects.update_or_create(
                etsy_listing_id=it["listing_id"],
                defaults={
                    "owner": user,
                    "title": it.get("title", ""),
                    "state": it.get("state", ""),
                    "url": it.get("url", ""),
                    "image_url_170x135": image_url_170x135,
                    "image_url_75x75": image_url_75x75,
                    "quantity": it.get("quantity"),
                    "price_amount": (it.get("price") or {}).get("amount"),
                    "price_currency": (it.get("price") or {}).get("currency_code", ""),
                },
            )
            # Bir ilanın varyasyon hatası diğer ilanların eşitlenmesini durdurmaz.
            try:
                inventory = inventory_by_id[it["listing_id"]]
                _sync_listing_variations(listing, (inventory or {}).get("products", []))
                variation_sync_ok += 1
            except Exception:
                variation_sync_failed += 1
                logger.exception(
                    "Variation sync failed for listing %s", listing.etsy_listing_id
                )
            listings_synced += 1

        offset += limit
        total_count = payload.get("count")
        if len(items) < limit or (total_count is not None and offset >= total_count):
            break

    # Arayüzde gösterilecek işlem sayılarını döndür.
    return {
        "listings_synced": listings_synced,
        "variation_sync_ok": variation_sync_ok,
        "variation_sync_failed": variation_sync_failed,
    }
