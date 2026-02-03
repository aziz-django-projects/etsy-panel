from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0005_order_buyer"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="canceled",
            field=models.BooleanField(default=False),
        ),
    ]
