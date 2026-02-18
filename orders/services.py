import json
import logging
from datetime import timedelta, timezone as dt_timezone

from django.utils import timezone

from etsy.client import EtsyClient
from etsy.models import EtsyAccount
from customers.models import Buyer

from .models import Order, OrderItem, Shipment
from .shipentegra import ShipentegraClient

logger = logging.getLogger(__name__)


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


def _extract_variation_label(variations):
    if not variations:
        return ""
    values = []
    for variation in variations:
        if not isinstance(variation, dict):
            continue
        value = (
            variation.get("formatted_value")
            or variation.get("value")
            or variation.get("value_name")
            or variation.get("value_id")
        )
        if value:
            values.append(str(value))
            continue
        name = (
            variation.get("formatted_name")
            or variation.get("property_name")
            or variation.get("name")
        )
        if name:
            values.append(str(name))
    return " / ".join(values)


def _extract_tracking(receipt):
    tracking_number = receipt.get("tracking_code")
    carrier_name = receipt.get("carrier_name", "")
    shipments = receipt.get("shipments") or []
    if not tracking_number and shipments:
        tracking_number = shipments[0].get("tracking_code") or shipments[0].get("tracking_number")
        carrier_name = carrier_name or shipments[0].get("carrier_name", "")
    return tracking_number or "", carrier_name or ""


def _extract_country_code(receipt):
    candidates = [
        receipt.get("country_iso"),
        (receipt.get("shipping_address") or {}).get("country_iso"),
        (receipt.get("shipping_address") or {}).get("country_code"),
        (receipt.get("shipping_address") or {}).get("country"),
    ]
    for value in candidates:
        if not isinstance(value, str):
            continue
        value = value.strip()
        if len(value) == 2 and value.isalpha():
            return value.upper()
    return ""


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
    if value is None:
        return ""
    return str(value).strip().lower()

def fetch_ship_status(tracking_number):
    client = ShipentegraClient()
    payload = client.get_shipment_activities(tracking_number)
    if not payload:
        return None
    if payload.get("status") != "success":
        return None

    data = payload.get("data") or {}
    status_text = data.get("status") or ""
    activities = data.get("activities") or []

    delivered_at = _parse_iso_datetime(data.get("deliveryDate"))

    last_activity_value = None
    if activities:
        last_activity = activities[0] or {}
        if last_activity.get("date"):
            last_activity_value = last_activity.get("date")
    last_activity_at = _parse_iso_datetime(last_activity_value) or delivered_at

    is_delivered = status_text.strip().upper() == "DELIVERED"
    return {
        "status": status_text,
        "delivered_at": delivered_at if is_delivered else None,
        "last_activity_at": last_activity_at,
        "is_delivered": is_delivered,
        "raw": json.dumps(data, ensure_ascii=False),
    }

def sync_orders(user):
    account = EtsyAccount.objects.get(user=user)
    client = EtsyClient(account)

    _ensure_shop(account, client)

    offset = 0
    limit = 50
    min_created_dt = (timezone.now() - timedelta(days=30)).astimezone(dt_timezone.utc)
    min_created = int(min_created_dt.timestamp())
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
            existing = (
                Order.objects.filter(etsy_order_id=etsy_order_id)
                .values("status", "archived", "canceled")
                .first()
            )
            existing_status = existing.get("status") if existing else None
            existing_archived = existing.get("archived") if existing else False
            existing_canceled = existing.get("canceled") if existing else False

            buyer_name = receipt.get("name") or ""
            buyer_email = receipt.get("buyer_email") or ""
            buyer_user_id = receipt.get("buyer_user_id")
            country_code = _extract_country_code(receipt)
            buyer = None
            if buyer_user_id:
                buyer_defaults = {"last_seen_at": timezone.now()}
                if buyer_name:
                    buyer_defaults["display_name"] = buyer_name
                if country_code:
                    buyer_defaults["country_code"] = country_code
                buyer, _ = Buyer.objects.update_or_create(
                    owner=user,
                    etsy_buyer_user_id=buyer_user_id,
                    defaults=buyer_defaults,
                )
            total_amount, currency = _extract_price(receipt)

            items = receipt.get("transactions") or []
            expected_ship_date = None
            expected_candidates = []
            for item in items:
                expected_value = item.get("expected_ship_date")
                if expected_value is None:
                    expected_value = item.get("expected_ship_date_timestamp")
                parsed = _parse_ts(expected_value)
                if parsed:
                    expected_candidates.append(parsed)
            if expected_candidates:
                expected_ship_date = min(expected_candidates)

            shipped_at = None
            shipments = receipt.get("shipments") or []
            if shipments:
                shipped_at = _parse_ts(shipments[0].get("shipment_notification_timestamp"))

            order_created_at = _parse_ts(receipt.get("created_timestamp"))
            receipt_status = _normalize_status(receipt.get("status"))
            is_canceled = receipt_status == "canceled"

            order, _ = Order.objects.update_or_create(
                etsy_order_id=etsy_order_id,
                defaults={
                    "owner": user,
                    "status": existing_status or Order.Status.RECEIVED,
                    "buyer": buyer,
                    "buyer_name": buyer_name,
                    "buyer_email": buyer_email,
                    "total_amount": total_amount,
                    "currency": currency,
                    "order_created_at": order_created_at,
                    "shipped_at": shipped_at,
                    "expected_ship_date": expected_ship_date,
                    "last_synced_at": timezone.now(),
                    "canceled": is_canceled,
                },
            )
            if order.canceled != is_canceled:
                order.canceled = is_canceled
                order.save(update_fields=["canceled"])
            if existing_status == Order.Status.CLOSED and order.status != Order.Status.CLOSED:
                order.status = Order.Status.CLOSED
                order.save(update_fields=["status"])
            if existing_archived and not order.archived:
                order.archived = True
                order.save(update_fields=["archived"])

            if items:
                seen_item_ids = set()
                for item in items:
                    variations = item.get("variations") or []
                    defaults = {
                        "etsy_listing_id": item.get("listing_id"),
                        "title": item.get("title", ""),
                        "quantity": item.get("quantity"),
                        "price_amount": (item.get("price") or {}).get("amount"),
                        "price_currency": (item.get("price") or {}).get(
                            "currency_code", ""
                        ),
                        "variation_label": _extract_variation_label(variations),
                        "variation_raw": variations,
                    }
                    tx_id = item.get("transaction_id")
                    if tx_id:
                        order_item, _ = OrderItem.objects.update_or_create(
                            order=order,
                            etsy_transaction_id=tx_id,
                            defaults=defaults,
                        )
                    else:
                        order_item = OrderItem.objects.create(order=order, **defaults)
                    seen_item_ids.add(order_item.id)
                if seen_item_ids:
                    stale_items = order.items.exclude(id__in=seen_item_ids)
                    stale_items = stale_items.exclude(stock_movements__isnull=False)
                    stale_items.delete()

            tracking_number, carrier_name = _extract_tracking(receipt)
            ship_status_value = ""
            if tracking_number:
                shipment, _ = Shipment.objects.get_or_create(order=order)
                shipment.tracking_number = tracking_number
                shipment.carrier_name = carrier_name
                shipment.shipped_at = shipped_at
                shipment.last_checked_at = timezone.now()

                ship_status = fetch_ship_status(tracking_number)
                if ship_status:
                    ship_status_value = _normalize_status(ship_status.get("status"))
                    shipment.carrier_status = ship_status.get("status", "")
                    shipment.carrier_status_raw = ship_status.get("raw", "")
                    shipment.last_activity_at = ship_status.get("last_activity_at")
                    shipment.delivered_at = ship_status.get("delivered_at") or ship_status.get(
                        "last_activity_at"
                    )
                    if ship_status.get("is_delivered"):
                        if shipment.delivered_at and not order.delivered_at:
                            order.delivered_at = shipment.delivered_at

                shipment.save()
                if order.delivered_at:
                    order.save(update_fields=["delivered_at"])

            if order.status != Order.Status.CLOSED and not is_canceled:
                status = None
                if receipt_status == "paid":
                    status = Order.Status.RECEIVED
                elif receipt_status == "completed":
                    if ship_status_value == "pending":
                        status = Order.Status.SHIPPED
                    elif ship_status_value in {"in transit", "in_transit"}:
                        status = Order.Status.IN_TRANSIT
                    elif ship_status_value == "delivered":
                        status = Order.Status.DELIVERED
                if status and order.status != status:
                    order.status = status
                    order.save(update_fields=["status"])

            try:
                from inventory.services import apply_stock_for_order_transition

                apply_stock_for_order_transition(
                    order, previous_status=existing_status, previous_canceled=existing_canceled
                )
            except Exception:
                logger.exception(
                    "Stock adjustment failed for order %s", order.etsy_order_id
                )

            total += 1

        offset += limit

    return total
