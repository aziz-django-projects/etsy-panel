from django.conf import settings
from django.db import models


class Order(models.Model):
    class Status(models.TextChoices):
        RECEIVED = "received", "Received"
        SHIPPED = "shipped", "Shipped"
        IN_TRANSIT = "in_transit", "In transit"
        DELIVERED = "delivered", "Delivered"
        CLOSED = "closed", "Closed"

    etsy_order_id = models.BigIntegerField(unique=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RECEIVED)
    buyer_name = models.CharField(max_length=255, blank=True)
    buyer_email = models.EmailField(blank=True)
    total_amount = models.IntegerField(null=True, blank=True)
    currency = models.CharField(max_length=10, blank=True)
    order_created_at = models.DateTimeField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    last_synced_at = models.DateTimeField(null=True, blank=True)

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.etsy_order_id} - {self.buyer_name}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, related_name="items", on_delete=models.CASCADE)
    etsy_listing_id = models.BigIntegerField(null=True, blank=True)
    title = models.CharField(max_length=255, blank=True)
    quantity = models.IntegerField(null=True, blank=True)
    price_amount = models.IntegerField(null=True, blank=True)
    price_currency = models.CharField(max_length=10, blank=True)

    def __str__(self):
        return f"{self.order_id} - {self.title}"


class Shipment(models.Model):
    order = models.OneToOneField(Order, related_name="shipment", on_delete=models.CASCADE)
    tracking_number = models.CharField(max_length=100, blank=True)
    carrier_name = models.CharField(max_length=100, blank=True)
    carrier_status = models.CharField(max_length=100, blank=True)
    carrier_status_raw = models.TextField(blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.order_id} - {self.tracking_number}"
