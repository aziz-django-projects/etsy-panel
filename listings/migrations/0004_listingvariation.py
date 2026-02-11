from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("listings", "0003_listing_image_urls"),
    ]

    operations = [
        migrations.CreateModel(
            name="ListingVariation",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("etsy_product_id", models.BigIntegerField()),
                ("label", models.CharField(blank=True, max_length=255)),
                ("property_values_raw", models.JSONField(blank=True, default=list)),
                ("value_ids", models.JSONField(blank=True, default=list)),
                ("is_deleted", models.BooleanField(default=False)),
                ("raw", models.JSONField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "listing",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="variations",
                        to="listings.listing",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="listingvariation",
            constraint=models.UniqueConstraint(
                fields=("listing", "etsy_product_id"),
                name="uniq_listing_variation_listing_product",
            ),
        ),
    ]
