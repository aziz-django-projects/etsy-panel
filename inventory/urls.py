from django.urls import path

from . import views

urlpatterns = [
    path("", views.inventory_home, name="inventory_home"),
    path("adjust/<int:bucket_id>/", views.adjust_bucket, name="inventory_adjust"),
]
