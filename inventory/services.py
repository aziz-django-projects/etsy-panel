import re

from django.db import transaction
from django.db.models import F

from .models import (
    InventoryProduct,
    InventoryRecipeItem,
    InventoryVariation,
    StockBucket,
    StockMovement,
)


FLOWER_BANNER_VARIATIONS = [
    "5 Banners - Small",
    "6 Banners - Small",
    "7 Banners - Small",
    "8 Banners - Small",
    "9 Banners - Small",
    "10 Banners - Small",
    "5 Banners - Large",
    "6 Banners - Large",
    "7 Banners - Large",
    "8 Banners - Large",
    "9 Banners - Large",
    "10 Banners - Large",
]


def _pennant_counts(total_banners: int) -> dict[int, int]:
    counts = {index: 0 for index in range(1, 6)}
    for offset in range(total_banners):
        bucket_index = (offset % 5) + 1
        counts[bucket_index] += 1
    return counts


def _bucket_name(index: int, size_suffix: str) -> str:
    return f"Pennant {index}-{size_suffix}"


def seed_flower_banner(owner, etsy_listing_id: int, product_name: str):
    product, _ = InventoryProduct.objects.update_or_create(
        owner=owner,
        etsy_listing_id=etsy_listing_id,
        defaults={"name": product_name, "is_active": True},
    )

    buckets = {}
    for suffix in ("S", "L"):
        for index in range(1, 6):
            bucket, _ = StockBucket.objects.update_or_create(
                owner=owner,
                product=product,
                name=_bucket_name(index, suffix),
                defaults={"is_active": True},
            )
            buckets[(index, suffix)] = bucket

    for variation_name in FLOWER_BANNER_VARIATIONS:
        variation, _ = InventoryVariation.objects.update_or_create(
            product=product,
            name=variation_name,
            defaults={"is_active": True},
        )
        suffix = "S"
        if "large" in variation_name.lower():
            suffix = "L"
        match = re.match(r"^(\\d+)\\s+Banners\\s+-\\s+", variation_name)
        if not match:
            continue
        total_banners = int(match.group(1))
        counts = _pennant_counts(total_banners)
        for index, amount in counts.items():
            InventoryRecipeItem.objects.update_or_create(
                variation=variation,
                bucket=buckets[(index, suffix)],
                defaults={"quantity": amount},
            )


def _extract_etsy_ids_from_order_variations(variations):
    property_ids = []
    value_ids = []
    for variation in variations or []:
        if not isinstance(variation, dict):
            continue

        property_id = variation.get("property_id")
        if property_id is not None:
            try:
                property_ids.append(int(property_id))
            except (TypeError, ValueError):
                pass

        value_id = variation.get("value_id")
        if value_id is not None:
            try:
                value_ids.append(int(value_id))
            except (TypeError, ValueError):
                pass

        value_id_list = variation.get("value_ids") or []
        if isinstance(value_id_list, list):
            for item in value_id_list:
                if item is None:
                    continue
                try:
                    value_ids.append(int(item))
                except (TypeError, ValueError):
                    continue

    return sorted(set(property_ids)), sorted(set(value_ids))


def _get_variation_for_item(order_item):
    label = (order_item.variation_label or "").strip()
    if not order_item.etsy_listing_id:
        return None

    property_ids, value_ids = _extract_etsy_ids_from_order_variations(
        order_item.variation_raw or []
    )
    if value_ids:
        qs = InventoryVariation.objects.select_related("product").filter(
            product__owner=order_item.order.owner,
            product__etsy_listing_id=order_item.etsy_listing_id,
            product__is_active=True,
            is_active=True,
            etsy_value_ids=value_ids,
        )
        if property_ids:
            qs = qs.filter(etsy_property_ids=property_ids)
        hit = qs.first()
        if hit:
            return hit

    if not label:
        return None
    return (
        InventoryVariation.objects.select_related("product")
        .filter(
            product__owner=order_item.order.owner,
            product__etsy_listing_id=order_item.etsy_listing_id,
            product__is_active=True,
            is_active=True,
            name__iexact=label,
        )
        .first()
    )


def _apply_bucket_delta(bucket, delta: int):
    if delta == 0:
        return
    StockBucket.objects.filter(id=bucket.id).update(quantity=F("quantity") + delta)


def _apply_deduction_for_item(order_item):
    quantity = int(order_item.quantity or 0)
    if quantity <= 0:
        return 0
    variation = _get_variation_for_item(order_item)
    if not variation:
        return 0

    created = 0
    recipe_items = list(
        InventoryRecipeItem.objects.select_related("bucket").filter(variation=variation)
    )
    if not recipe_items:
        return 0

    with transaction.atomic():
        for recipe_item in recipe_items:
            delta = -(recipe_item.quantity * quantity)
            movement, movement_created = StockMovement.objects.get_or_create(
                owner=order_item.order.owner,
                order=order_item.order,
                order_item=order_item,
                variation=variation,
                bucket=recipe_item.bucket,
                reason=StockMovement.Reason.SHIP_DEDUCT,
                defaults={"delta": delta},
            )
            if movement_created:
                _apply_bucket_delta(recipe_item.bucket, delta)
                created += 1
    return created


def _apply_restock_for_item(order_item):
    shipped_moves = list(
        StockMovement.objects.select_related("bucket").filter(
            order_item=order_item,
            reason=StockMovement.Reason.SHIP_DEDUCT,
        )
    )
    if not shipped_moves:
        return 0
    already_restocked = StockMovement.objects.filter(
        order_item=order_item,
        reason=StockMovement.Reason.CANCEL_RESTOCK,
    ).exists()
    if already_restocked:
        return 0

    created = 0
    with transaction.atomic():
        for move in shipped_moves:
            delta = -move.delta
            movement, movement_created = StockMovement.objects.get_or_create(
                owner=move.owner,
                order=move.order,
                order_item=order_item,
                variation=move.variation,
                bucket=move.bucket,
                reason=StockMovement.Reason.CANCEL_RESTOCK,
                defaults={"delta": delta},
            )
            if movement_created:
                _apply_bucket_delta(move.bucket, delta)
                created += 1
    return created


def apply_stock_for_order_transition(order, previous_status, previous_canceled):
    from orders.models import Order

    if (
        order.status == Order.Status.SHIPPED
        and previous_status != Order.Status.SHIPPED
        and not order.canceled
    ):
        for item in order.items.all():
            _apply_deduction_for_item(item)

    if order.canceled and not previous_canceled:
        for item in order.items.all():
            _apply_restock_for_item(item)
