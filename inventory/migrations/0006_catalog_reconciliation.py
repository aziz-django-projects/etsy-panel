from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0005_inventoryvariation_etsy_ids"),
    ]

    operations = [
        migrations.AddField(
            model_name="inventoryvariation",
            name="etsy_product_id",
            field=models.BigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="inventoryvariation",
            name="etsy_available",
            field=models.BooleanField(default=True),
        ),
        migrations.RemoveConstraint(
            model_name="inventoryvariation",
            name="uniq_inventory_variation_product_name",
        ),
        migrations.AddConstraint(
            model_name="inventoryvariation",
            constraint=models.UniqueConstraint(
                fields=("product", "etsy_product_id"),
                condition=Q(etsy_product_id__isnull=False),
                name="uniq_inventory_variation_product_etsy_id",
            ),
        ),
    ]
