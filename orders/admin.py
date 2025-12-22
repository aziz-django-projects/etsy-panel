from django.contrib import admin

from .models import Order, OrderItem, Shipment


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


class ShipmentInline(admin.StackedInline):
    model = Shipment
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("etsy_order_id", "buyer_name", "status", "owner", "last_synced_at")
    list_filter = ("status",)
    search_fields = ("etsy_order_id", "buyer_name", "buyer_email")
    inlines = (OrderItemInline, ShipmentInline)
