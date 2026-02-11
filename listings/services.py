import logging

from etsy.client import EtsyClient
from etsy.models import EtsyAccount

from .models import Listing, ListingVariation

logger = logging.getLogger(__name__)


def _extract_variation_label(property_values):
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


def _sync_listing_variations(client, listing):
    payload = client.get_listing_inventory(listing.etsy_listing_id)
    products = payload.get("products", [])
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

    ListingVariation.objects.filter(listing=listing).exclude(
        etsy_product_id__in=seen_product_ids
    ).delete()
    ListingVariation.objects.filter(listing=listing, label="").delete()
    return len(seen_product_ids)


def sync_active_listings(user):
    account = EtsyAccount.objects.get(user=user)
    client = EtsyClient(account)

    # Shop_id yoksa önce shop’ları çek
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



    # Active listings çek (sayfalı)
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

        for it in items:
            image_url_170x135 = ""
            image_url_75x75 = ""
            try:
                images_payload = client.get_listing_images(it["listing_id"])
                image_results = images_payload.get("results", [])
                if image_results:
                    image_url_170x135 = image_results[0].get("url_170x135", "")
                    image_url_75x75 = image_results[0].get("url_75x75", "")
            except Exception:
                image_url_170x135 = ""
                image_url_75x75 = ""

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
            try:
                _sync_listing_variations(client, listing)
                variation_sync_ok += 1
            except Exception:
                variation_sync_failed += 1
                logger.exception(
                    "Variation sync failed for listing %s", listing.etsy_listing_id
                )
            listings_synced += 1

        offset += limit

    return {
        "listings_synced": listings_synced,
        "variation_sync_ok": variation_sync_ok,
        "variation_sync_failed": variation_sync_failed,
    }
