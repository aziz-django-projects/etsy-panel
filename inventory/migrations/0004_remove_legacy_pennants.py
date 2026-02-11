from django.db import migrations


def remove_legacy_pennants(apps, schema_editor):
    StockBucket = apps.get_model("inventory", "StockBucket")
    InventoryProduct = apps.get_model("inventory", "InventoryProduct")
    InventoryRecipeItem = apps.get_model("inventory", "InventoryRecipeItem")
    StockMovement = apps.get_model("inventory", "StockMovement")

    for product in InventoryProduct.objects.all():
        for index in range(1, 6):
            legacy_name = f"Pennant {index}"
            target_name = f"Pennant {index}-S"
            legacy_buckets = list(
                StockBucket.objects.filter(product=product, name=legacy_name)
            )
            if not legacy_buckets:
                continue
            target_bucket = StockBucket.objects.filter(
                product=product, name=target_name
            ).first()
            if not target_bucket:
                continue

            for legacy in legacy_buckets:
                if legacy.quantity:
                    target_bucket.quantity += legacy.quantity
                    target_bucket.save(update_fields=["quantity"])
                InventoryRecipeItem.objects.filter(bucket=legacy).update(
                    bucket=target_bucket
                )
                StockMovement.objects.filter(bucket=legacy).update(bucket=target_bucket)
                legacy.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0003_pennant_size_buckets"),
    ]

    operations = [
        migrations.RunPython(remove_legacy_pennants, migrations.RunPython.noop),
    ]
