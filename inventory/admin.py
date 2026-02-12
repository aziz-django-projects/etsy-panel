from django.contrib import admin

from .models import (
    InventoryProduct,
    InventoryRecipeItem,
    InventoryVariation,
    StockBucket,
    StockMovement,
)


@admin.register(StockBucket)
class StockBucketAdmin(admin.ModelAdmin):
    list_display = ("name", "product", "owner", "quantity", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("name", "product__name", "owner__username", "owner__email")


@admin.register(InventoryProduct)
class InventoryProductAdmin(admin.ModelAdmin):
    list_display = ("name", "etsy_listing_id", "owner", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "etsy_listing_id", "owner__username", "owner__email")


@admin.register(InventoryVariation)
class InventoryVariationAdmin(admin.ModelAdmin):
    list_display = ("name", "product", "is_active", "etsy_value_ids")
    list_filter = ("is_active",)
    search_fields = ("name", "product__name", "product__etsy_listing_id")


@admin.register(InventoryRecipeItem)
class InventoryRecipeItemAdmin(admin.ModelAdmin):
    list_display = ("variation", "bucket", "quantity")
    search_fields = ("variation__name", "bucket__name")


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ("bucket", "delta", "reason", "order", "order_item", "created_at")
    list_filter = ("reason", "bucket")
    search_fields = ("order__etsy_order_id", "bucket__name")
