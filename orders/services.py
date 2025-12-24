import json
from datetime import timezone as dt_timezone

from django.utils import timezone

from etsy.client import EtsyClient
from etsy.models import EtsyAccount

from .models import Order, OrderItem, Shipment
from .shipentegra import ShipentegraClient


def _ensure_shop(account, client):
    if account.shop_id:
        return

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


def _extract_price(payload):
    for key in ("total_price", "grandtotal", "price"):
        price = payload.get(key)
        if isinstance(price, dict):
            return price.get("amount"), price.get("currency_code", "")
    return None, ""


def _extract_tracking(receipt):
    tracking_number = receipt.get("tracking_code")
    carrier_name = receipt.get("carrier_name", "")
    shipments = receipt.get("shipments") or []
    if not tracking_number and shipments:
        tracking_number = shipments[0].get("tracking_code") or shipments[0].get("tracking_number")
        carrier_name = carrier_name or shipments[0].get("carrier_name", "")
    return tracking_number or "", carrier_name or ""

def _parse_ts(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return timezone.datetime.fromtimestamp(value, tz=dt_timezone.utc)
    return value


def _parse_iso_datetime(value):
    if not value:
        return None
    if isinstance(value, (int, float)):
        return timezone.datetime.fromtimestamp(value, tz=dt_timezone.utc)
    if not isinstance(value, str):
        return None
    value = value.strip()
    if not value:
        return None
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        parsed = timezone.datetime.fromisoformat(value)
    except ValueError:
        return None
    if timezone.is_naive(parsed):
        parsed = parsed.replace(tzinfo=dt_timezone.utc)
    return parsed


def _normalize_status(value):
    return (value or "").strip().lower()


DELIVERED_KEYWORDS = {
    "delivered",
    "completed",
    "teslim",
    "delivered_successfully",
}
IN_TRANSIT_KEYWORDS = {
    "in_transit",
    "in transit",
    "yolda",
    "out_for_delivery",
    "out for delivery",
    "shipped",
}


def _matches_keywords(value, keywords):
    if not value:
        return False
    return any(keyword in value for keyword in keywords)


def fetch_ship_status(tracking_number):
    client = ShipentegraClient()
    payload = client.get_shipment_activities(tracking_number)
    if not payload:
        return None
    if payload.get("status") != "success":
        return None

    data = payload.get("data") or {}
    status_text = data.get("status") or ""
    summary_text = data.get("summary") or ""
    activities = data.get("activities") or []
    last_event = ""
    if activities:
        last_event = activities[-1].get("event") or ""

    normalized = _normalize_status(" ".join([status_text, summary_text, last_event]))
    delivered_at = _parse_iso_datetime(data.get("deliveryDate"))

    is_delivered = _matches_keywords(normalized, DELIVERED_KEYWORDS)
    is_in_transit = _matches_keywords(normalized, IN_TRANSIT_KEYWORDS)
    if is_delivered:
        is_in_transit = False
    if not is_delivered:
        delivered_at = None

    status_display = status_text or summary_text or last_event or "Bilinmiyor"

    return {
        "status": status_display,
        "normalized": normalized,
        "delivered_at": delivered_at,
        "is_delivered": is_delivered,
        "is_in_transit": is_in_transit,
        "raw": json.dumps(payload, ensure_ascii=True),
    }


def send_etsy_message(_client, _order):
    # TODO: Etsy Messaging API ile teslim mesaji gonder.
    return False


def sync_orders(user):
    account = EtsyAccount.objects.get(user=user)
    client = EtsyClient(account.access_token)

    _ensure_shop(account, client)

    offset = 0
    limit = 50
    min_created = int((timezone.now() - timezone.timedelta(days=30)).timestamp())
    total = 0

    while True:
        payload = client.get_shop_receipts(
            shop_id=account.shop_id,
            limit=limit,
            offset=offset,
            min_created=min_created,
        )
        receipts = payload.get("results", [])
        if not receipts:
            break

        for receipt in receipts:
            etsy_order_id = receipt.get("receipt_id")
            if not etsy_order_id:
                continue
            existing_status = (
                Order.objects.filter(etsy_order_id=etsy_order_id)
                .values_list("status", flat=True)
                .first()
            )

            buyer_name = receipt.get("name") or ""
            buyer_email = receipt.get("buyer_email") or ""
            total_amount, currency = _extract_price(receipt)
            is_shipped = receipt.get("is_shipped")

            status = Order.Status.RECEIVED
            shipped_at = None
            if is_shipped:
                status = Order.Status.SHIPPED
                shipments = receipt.get("shipments") or []
                shipped_at = _parse_ts(shipments[0].get("shipment_notification_timestamp"))

            order_created_at = _parse_ts(receipt.get("created_timestamp"))

            order, _ = Order.objects.update_or_create(
                etsy_order_id=etsy_order_id,
                defaults={
                    "owner": user,
                    "status": status,
                    "buyer_name": buyer_name,
                    "buyer_email": buyer_email,
                    "total_amount": total_amount,
                    "currency": currency,
                    "order_created_at": order_created_at,
                    "shipped_at": shipped_at,
                    "last_synced_at": timezone.now(),
                },
            )
            if existing_status == Order.Status.CLOSED and order.status != Order.Status.CLOSED:
                order.status = Order.Status.CLOSED
                order.save(update_fields=["status"])

            items = receipt.get("transactions") or []
            if items:
                order.items.all().delete()
                for item in items:
                    OrderItem.objects.create(
                        order=order,
                        etsy_listing_id=item.get("listing_id"),
                        title=item.get("title", ""),
                        quantity=item.get("quantity"),
                        price_amount=(item.get("price") or {}).get("amount"),
                        price_currency=(item.get("price") or {}).get("currency_code", ""),
                    )

            tracking_number, carrier_name = _extract_tracking(receipt)
            if tracking_number:
                shipment, _ = Shipment.objects.get_or_create(order=order)
                shipment.tracking_number = tracking_number
                shipment.carrier_name = carrier_name
                shipment.shipped_at = shipped_at
                shipment.last_checked_at = timezone.now()

                ship_status = fetch_ship_status(tracking_number)
                if ship_status:
                    shipment.carrier_status = ship_status.get("status", "")
                    shipment.carrier_status_raw = ship_status.get("raw", "")
                    shipment.delivered_at = ship_status.get("delivered_at")
                    if ship_status.get("is_delivered"):
                        if shipment.delivered_at and not order.delivered_at:
                            order.delivered_at = shipment.delivered_at
                        if order.status != Order.Status.CLOSED and order.status != Order.Status.DELIVERED:
                            order.status = Order.Status.DELIVERED
                            send_etsy_message(client, order)
                    elif ship_status.get("is_in_transit"):
                        if order.status not in {Order.Status.DELIVERED, Order.Status.CLOSED}:
                            order.status = Order.Status.IN_TRANSIT

                shipment.save()
                order.save(update_fields=["status", "delivered_at"])

            total += 1

        offset += limit

    return total
