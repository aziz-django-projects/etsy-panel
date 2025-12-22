from django.urls import path

from . import views

urlpatterns = [
    path("", views.order_list, name="orders_home"),
    path("sync/", views.sync_now, name="orders_sync"),
]
