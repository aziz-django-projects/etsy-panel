"""Reconcile Etsy catalogue records with local inventory mappings.

Only catalogue identity and names are copied. Stock buckets, recipes, stock
movements, and the locally controlled ``is_active`` flags are left untouched.
"""

from django.db import transaction

from listings.models import ListingVariation

from .models import InventoryProduct, InventoryVariation


def _property_ids(property_values):
    ids = set()
    for value in property_values or []:
        if not isinstance(value, dict):
            continue
        property_id = value.get("property_id")
        if property_id is not None:
            try:
                ids.add(int(property_id))
            except (TypeError, ValueError):
                continue
    return sorted(ids)


def _value_ids(values):
    ids = set()
    for value in values or []:
        try:
            ids.add(int(value))
        except (TypeError, ValueError):
            continue
    return sorted(ids)


def _unique_legacy_match(variations, used_ids, *, name, property_ids, value_ids):
    """Attach existing manual mappings only when the match is unambiguous."""
    available = [
        variation
        for variation in variations
        if variation.etsy_product_id is None and variation.id not in used_ids
    ]
    if value_ids:
        matches = [
            variation
            for variation in available
            if _value_ids(variation.etsy_value_ids) == value_ids
            and (
                not property_ids
                or not variation.etsy_property_ids
                or _value_ids(variation.etsy_property_ids) == property_ids
            )
        ]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            return None

    matches = [
        variation for variation in available if variation.name.casefold() == name.casefold()
    ]
    return matches[0] if len(matches) == 1 else None


def reconcile_listing(listing, active_product_ids=None):
    """Update the local catalogue mapping after one successful listing sync.

    ``active_product_ids=None`` means Etsy did not supply complete inventory,
    so no variation is marked unavailable and no variation is created.
    """
    with transaction.atomic():
        product, _ = InventoryProduct.objects.get_or_create(
            owner=listing.owner,
            etsy_listing_id=listing.etsy_listing_id,
            defaults={"name": listing.title},
        )
        if listing.title and product.name != listing.title:
            product.name = listing.title
            product.save(update_fields=["name"])

        if active_product_ids is None:
            return product

        active_ids = set(active_product_ids)
        variations = list(InventoryVariation.objects.filter(product=product))
        by_etsy_id = {
            variation.etsy_product_id: variation
            for variation in variations
            if variation.etsy_product_id is not None
        }
        used_ids = set()

        listing_variations = ListingVariation.objects.filter(
            listing=listing, is_deleted=False
        ).exclude(label="")
        for source in listing_variations:
            property_ids = _property_ids(source.property_values_raw)
            value_ids = _value_ids(source.value_ids)
            variation = by_etsy_id.get(source.etsy_product_id)
            if variation is None:
                variation = _unique_legacy_match(
                    variations,
                    used_ids,
                    name=source.label,
                    property_ids=property_ids,
                    value_ids=value_ids,
                )

            if variation is None:
                variation = InventoryVariation.objects.create(
                    product=product,
                    name=source.label,
                    etsy_product_id=source.etsy_product_id,
                    etsy_property_ids=property_ids,
                    etsy_value_ids=value_ids,
                )
                variations.append(variation)
            else:
                changes = {}
                for field, value in {
                    "name": source.label,
                    "etsy_product_id": source.etsy_product_id,
                    "etsy_property_ids": property_ids,
                    "etsy_value_ids": value_ids,
                    "etsy_available": True,
                }.items():
                    if getattr(variation, field) != value:
                        changes[field] = value
                if changes:
                    for field, value in changes.items():
                        setattr(variation, field, value)
                    variation.save(update_fields=list(changes))
            used_ids.add(variation.id)

        InventoryVariation.objects.filter(
            product=product, etsy_product_id__isnull=False
        ).exclude(etsy_product_id__in=active_ids).update(etsy_available=False)
        return product
