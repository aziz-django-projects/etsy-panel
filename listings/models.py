from django.db import models
from django.conf import settings


class Listing(models.Model):
    etsy_listing_id = models.BigIntegerField(unique=True)
    title = models.CharField(max_length=255, blank=True)
    state = models.CharField(max_length=50, blank=True)  # active vs
    url = models.URLField(blank=True)
    image_url_170x135 = models.URLField(blank=True, default="")
    image_url_75x75 = models.URLField(blank=True, default="")
    price_amount = models.IntegerField(null=True, blank=True)   # cents gibi
    price_currency = models.CharField(max_length=10, blank=True)
    quantity = models.IntegerField(null=True, blank=True)

    # ileride multi-account için:
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    updated_at_etsy = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.etsy_listing_id} - {self.title}"


class ListingVariation(models.Model):
    listing = models.ForeignKey(
        Listing, related_name="variations", on_delete=models.CASCADE
    )
    etsy_product_id = models.BigIntegerField()
    label = models.CharField(max_length=255, blank=True)
    property_values_raw = models.JSONField(default=list, blank=True)
    value_ids = models.JSONField(default=list, blank=True)
    is_deleted = models.BooleanField(default=False)
    raw = models.JSONField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["listing", "etsy_product_id"],
                name="uniq_listing_variation_listing_product",
            )
        ]

    def __str__(self):
        return f"{self.listing_id} - {self.label or self.etsy_product_id}"
