from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from inventory.models import InventoryProduct, InventoryVariation
from listings.models import ListingVariation


def _norm(value: str) -> str:
    return (value or "").strip().lower()


def _extract_property_ids(listing_variation: ListingVariation) -> list[int]:
    property_ids: list[int] = []
    for pv in listing_variation.property_values_raw or []:
        if not isinstance(pv, dict):
            continue
        prop_id = pv.get("property_id")
        if prop_id is None:
            continue
        try:
            property_ids.append(int(prop_id))
        except (TypeError, ValueError):
            continue
    return sorted(set(property_ids))


def _extract_value_ids(listing_variation: ListingVariation) -> list[int]:
    value_ids: list[int] = []
    for value_id in listing_variation.value_ids or []:
        if value_id is None:
            continue
        try:
            value_ids.append(int(value_id))
        except (TypeError, ValueError):
            continue
    return sorted(set(value_ids))


class Command(BaseCommand):
    help = "Populate InventoryVariation Etsy IDs from listings.ListingVariation."

    def add_arguments(self, parser):
        parser.add_argument("--user-id", type=int, required=True)
        parser.add_argument("--listing-id", type=int, required=True)
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would change without writing to DB.",
        )

    def handle(self, *args, **options):
        user_id = options["user_id"]
        listing_id = int(options["listing_id"])
        dry_run = bool(options["dry_run"])

        User = get_user_model()
        try:
            owner = User.objects.get(id=user_id)
        except User.DoesNotExist as exc:
            raise CommandError(f"User not found: {user_id}") from exc

        try:
            product = InventoryProduct.objects.get(owner=owner, etsy_listing_id=listing_id)
        except InventoryProduct.DoesNotExist as exc:
            raise CommandError(
                f"InventoryProduct not found for user_id={user_id} listing_id={listing_id}"
            ) from exc

        listing_vars = list(
            ListingVariation.objects.filter(
                listing__owner=owner, listing__etsy_listing_id=listing_id, label__gt=""
            )
        )
        by_label: dict[str, ListingVariation] = {}
        duplicates = 0
        for lv in listing_vars:
            key = _norm(lv.label)
            if not key:
                continue
            if key in by_label:
                duplicates += 1
                continue
            by_label[key] = lv

        updated = 0
        unchanged = 0
        skipped = 0

        variations = list(InventoryVariation.objects.filter(product=product))
        for inv in variations:
            lv = by_label.get(_norm(inv.name))
            if not lv:
                skipped += 1
                continue

            property_ids = _extract_property_ids(lv)
            value_ids = _extract_value_ids(lv)

            if inv.etsy_property_ids == property_ids and inv.etsy_value_ids == value_ids:
                unchanged += 1
                continue

            if not dry_run:
                inv.etsy_property_ids = property_ids
                inv.etsy_value_ids = value_ids
                inv.save(update_fields=["etsy_property_ids", "etsy_value_ids"])

            updated += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Sync complete: updated={updated} unchanged={unchanged} skipped={skipped} "
                f"duplicates_in_listing={duplicates} dry_run={dry_run}"
            )
        )

