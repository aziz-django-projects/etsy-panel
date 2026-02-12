from django.conf import settings
from django.db import models
from django.db.models import Q


class InventoryProduct(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    etsy_listing_id = models.BigIntegerField()
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "etsy_listing_id"],
                name="uniq_inventory_product_owner_listing",
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.etsy_listing_id})"


class StockBucket(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    product = models.ForeignKey(
        InventoryProduct, related_name="stock_buckets", on_delete=models.CASCADE
    )
    name = models.CharField(max_length=100)
    quantity = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["product", "name"], name="uniq_stock_bucket_product_name"
            )
        ]

    def __str__(self):
        return f"{self.product.name} - {self.name} ({self.quantity})"


class InventoryVariation(models.Model):
    product = models.ForeignKey(
        InventoryProduct, related_name="variations", on_delete=models.CASCADE
    )
    name = models.CharField(max_length=255)
    etsy_property_ids = models.JSONField(default=list, blank=True)
    etsy_value_ids = models.JSONField(default=list, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["product", "name"], name="uniq_inventory_variation_product_name"
            )
        ]

    def __str__(self):
        return f"{self.product.name} - {self.name}"


class InventoryRecipeItem(models.Model):
    variation = models.ForeignKey(
        InventoryVariation, related_name="recipe_items", on_delete=models.CASCADE
    )
    bucket = models.ForeignKey(StockBucket, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["variation", "bucket"],
                name="uniq_inventory_recipe_variation_bucket",
            )
        ]

    def __str__(self):
        return f"{self.variation.name}: {self.bucket.name} x{self.quantity}"


class StockMovement(models.Model):
    class Reason(models.TextChoices):
        SHIP_DEDUCT = "ship_deduct", "Shipped deduction"
        CANCEL_RESTOCK = "cancel_restock", "Canceled restock"
        MANUAL = "manual", "Manual adjustment"

    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    bucket = models.ForeignKey(
        StockBucket, related_name="movements", on_delete=models.CASCADE
    )
    order = models.ForeignKey(
        "orders.Order",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="stock_movements",
    )
    order_item = models.ForeignKey(
        "orders.OrderItem",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="stock_movements",
    )
    variation = models.ForeignKey(
        InventoryVariation,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="stock_movements",
    )
    delta = models.IntegerField()
    reason = models.CharField(max_length=30, choices=Reason.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["order_item", "bucket", "reason"],
                condition=Q(order_item__isnull=False),
                name="uniq_stock_move_item_bucket_reason",
            )
        ]

    def __str__(self):
        return f"{self.bucket.name} {self.delta} ({self.reason})"
