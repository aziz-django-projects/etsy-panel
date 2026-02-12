from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0004_remove_legacy_pennants"),
    ]

    operations = [
        migrations.AddField(
            model_name="inventoryvariation",
            name="etsy_property_ids",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="inventoryvariation",
            name="etsy_value_ids",
            field=models.JSONField(blank=True, default=list),
        ),
    ]

