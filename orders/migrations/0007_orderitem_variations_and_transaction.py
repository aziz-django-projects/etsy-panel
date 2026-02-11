from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0006_order_canceled"),
    ]

    operations = [
        migrations.AddField(
            model_name="orderitem",
            name="etsy_transaction_id",
            field=models.BigIntegerField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="variation_label",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="variation_raw",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="orderitem",
            constraint=models.UniqueConstraint(
                condition=Q(("etsy_transaction_id__isnull", False)),
                fields=("order", "etsy_transaction_id"),
                name="uniq_order_item_transaction",
            ),
        ),
    ]
