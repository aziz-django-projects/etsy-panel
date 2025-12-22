from django.utils import timezone
from datetime import timezone as dt_timezone

from etsy.client import EtsyClient
from etsy.models import EtsyAccount

from .models import Order, OrderItem, Shipment


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

def _parse_ts(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return timezone.datetime.fromtimestamp(value, tz=dt_timezone.utc)
    return value


def fetch_ship_status(_tracking_number):
    # TODO: Ship entegre API ile sorgu yapilacak.
    return None


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

            tracking_number = receipt.get("tracking_code", "")
            if tracking_number:
                shipment, _ = Shipment.objects.get_or_create(order=order)
                shipment.tracking_number = tracking_number
                shipment.carrier_name = receipt.get("carrier_name", "")
                shipment.shipped_at = shipped_at
                shipment.last_checked_at = timezone.now()

                ship_status = fetch_ship_status(tracking_number)
                if ship_status:
                    shipment.carrier_status = ship_status.get("status", "")
                    shipment.carrier_status_raw = ship_status.get("raw", "")
                    shipment.delivered_at = ship_status.get("delivered_at")
                    if shipment.delivered_at:
                        order.status = Order.Status.DELIVERED
                        order.delivered_at = shipment.delivered_at
                        send_etsy_message(client, order)

                shipment.save()
                order.save(update_fields=["status", "delivered_at"])

            total += 1

        offset += limit

    return total
