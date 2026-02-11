from django.contrib import admin

from .models import Listing, ListingVariation


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ("etsy_listing_id", "title", "owner", "quantity", "state")
    search_fields = ("etsy_listing_id", "title", "owner__username", "owner__email")


@admin.register(ListingVariation)
class ListingVariationAdmin(admin.ModelAdmin):
    list_display = ("etsy_product_id", "label", "listing", "is_deleted", "updated_at")
    search_fields = ("etsy_product_id", "label", "listing__title", "listing__etsy_listing_id")
