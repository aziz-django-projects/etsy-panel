from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("orders", "0006_order_canceled"),
    ]

    operations = [
        migrations.CreateModel(
            name="InventoryProduct",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                ("etsy_listing_id", models.BigIntegerField()),
                ("is_active", models.BooleanField(default=True)),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={},
        ),
        migrations.CreateModel(
            name="InventoryVariation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=255)),
                ("is_active", models.BooleanField(default=True)),
                ("product", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="variations", to="inventory.inventoryproduct")),
            ],
            options={},
        ),
        migrations.CreateModel(
            name="StockBucket",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100)),
                ("quantity", models.IntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={},
        ),
        migrations.CreateModel(
            name="InventoryRecipeItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.PositiveIntegerField()),
                ("bucket", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="inventory.stockbucket")),
                ("variation", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="recipe_items", to="inventory.inventoryvariation")),
            ],
            options={},
        ),
        migrations.CreateModel(
            name="StockMovement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("delta", models.IntegerField()),
                ("reason", models.CharField(choices=[("ship_deduct", "Shipped deduction"), ("cancel_restock", "Canceled restock"), ("manual", "Manual adjustment")], max_length=30)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("bucket", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="movements", to="inventory.stockbucket")),
                ("order", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="stock_movements", to="orders.order")),
                ("order_item", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="stock_movements", to="orders.orderitem")),
                ("owner", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ("variation", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="stock_movements", to="inventory.inventoryvariation")),
            ],
            options={},
        ),
        migrations.AddConstraint(
            model_name="stockbucket",
            constraint=models.UniqueConstraint(fields=("owner", "name"), name="uniq_stock_bucket_owner_name"),
        ),
        migrations.AddConstraint(
            model_name="inventoryproduct",
            constraint=models.UniqueConstraint(fields=("owner", "etsy_listing_id"), name="uniq_inventory_product_owner_listing"),
        ),
        migrations.AddConstraint(
            model_name="inventoryvariation",
            constraint=models.UniqueConstraint(fields=("product", "name"), name="uniq_inventory_variation_product_name"),
        ),
        migrations.AddConstraint(
            model_name="inventoryrecipeitem",
            constraint=models.UniqueConstraint(fields=("variation", "bucket"), name="uniq_inventory_recipe_variation_bucket"),
        ),
        migrations.AddConstraint(
            model_name="stockmovement",
            constraint=models.UniqueConstraint(condition=models.Q(("order_item__isnull", False)), fields=("order_item", "bucket", "reason"), name="uniq_stock_move_item_bucket_reason"),
        ),
    ]
