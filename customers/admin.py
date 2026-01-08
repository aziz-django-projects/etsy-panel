from django.contrib import admin

from .models import Buyer


@admin.register(Buyer)
class BuyerAdmin(admin.ModelAdmin):
    list_display = ("etsy_buyer_user_id", "display_name", "country_code", "owner", "last_seen_at")
    list_filter = ("country_code",)
    search_fields = ("etsy_buyer_user_id", "display_name")

