from django.db import migrations, models
import django.db.models.deletion


def assign_buckets_to_product(apps, schema_editor):
    StockBucket = apps.get_model("inventory", "StockBucket")
    InventoryProduct = apps.get_model("inventory", "InventoryProduct")

    buckets = StockBucket.objects.filter(product__isnull=True)
    for bucket in buckets:
        product = (
            InventoryProduct.objects.filter(owner=bucket.owner).order_by("id").first()
        )
        if product:
            bucket.product = product
            bucket.save(update_fields=["product"])


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="stockbucket",
            name="product",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="stock_buckets",
                to="inventory.inventoryproduct",
            ),
        ),
        migrations.RunPython(assign_buckets_to_product, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="stockbucket",
            name="product",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="stock_buckets",
                to="inventory.inventoryproduct",
            ),
        ),
        migrations.RemoveConstraint(
            model_name="stockbucket",
            name="uniq_stock_bucket_owner_name",
        ),
        migrations.AddConstraint(
            model_name="stockbucket",
            constraint=models.UniqueConstraint(
                fields=("product", "name"),
                name="uniq_stock_bucket_product_name",
            ),
        ),
    ]
