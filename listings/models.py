from django.db import models
from django.conf import settings

class Listing(models.Model):
    etsy_listing_id = models.BigIntegerField(unique=True)
    title = models.CharField(max_length=255, blank=True)
    state = models.CharField(max_length=50, blank=True)  # active vs
    url = models.URLField(blank=True)
    price_amount = models.IntegerField(null=True, blank=True)   # cents gibi
    price_currency = models.CharField(max_length=10, blank=True)
    quantity = models.IntegerField(null=True, blank=True)

    # ileride multi-account için:
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    updated_at_etsy = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.etsy_listing_id} - {self.title}"
