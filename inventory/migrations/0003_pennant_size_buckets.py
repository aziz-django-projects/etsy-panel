import re

from django.db import migrations


def _extract_index(name: str):
    match = re.search(r"(\\d+)", name)
    if match:
        return int(match.group(1))
    return None


def split_pennant_buckets(apps, schema_editor):
    InventoryProduct = apps.get_model("inventory", "InventoryProduct")
    StockBucket = apps.get_model("inventory", "StockBucket")
    InventoryVariation = apps.get_model("inventory", "InventoryVariation")
    InventoryRecipeItem = apps.get_model("inventory", "InventoryRecipeItem")

    for product in InventoryProduct.objects.all():
        buckets = list(StockBucket.objects.filter(product=product))
        existing = {(bucket.name): bucket for bucket in buckets}

        # Rename old Pennant N buckets to Pennant N-S
        for bucket in buckets:
            if re.match(r"^Pennant\\s+\\d+$", bucket.name):
                index = _extract_index(bucket.name)
                if not index:
                    continue
                new_name = f"Pennant {index}-S"
                if new_name not in existing:
                    bucket.name = new_name
                    bucket.save(update_fields=["name"])
                    existing[new_name] = bucket

        # Ensure both S and L buckets exist
        for index in range(1, 6):
            for suffix in ("S", "L"):
                name = f"Pennant {index}-{suffix}"
                if name in existing:
                    continue
                bucket = StockBucket.objects.create(
                    owner=product.owner,
                    product=product,
                    name=name,
                    quantity=0,
                    is_active=True,
                )
                existing[name] = bucket

        # Remap recipe items for Large variations to L buckets
        large_variations = InventoryVariation.objects.filter(
            product=product, name__icontains="large"
        )
        for variation in large_variations:
            for item in InventoryRecipeItem.objects.filter(variation=variation):
                index = _extract_index(item.bucket.name)
                if not index:
                    continue
                target_name = f"Pennant {index}-L"
                target_bucket = existing.get(target_name)
                if target_bucket and item.bucket_id != target_bucket.id:
                    item.bucket_id = target_bucket.id
                    item.save(update_fields=["bucket"])


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0002_stockbucket_product"),
    ]

    operations = [
        migrations.RunPython(split_pennant_buckets, migrations.RunPython.noop),
    ]
