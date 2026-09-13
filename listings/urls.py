from django.urls import path
from .views import ListingsHomeView, set_inventory_tracking

urlpatterns = [
    path("", ListingsHomeView.as_view(), name="listings_home"),
    path(
        "<int:listing_id>/inventory-tracking/",
        set_inventory_tracking,
        name="listing_inventory_tracking",
    ),
]
