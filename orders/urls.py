from django.urls import path

from . import views

urlpatterns = [
    path("", views.order_list, name="orders_home"),
    path("sync/", views.sync_now, name="orders_sync"),
    path("close/<int:order_id>/", views.close_order, name="orders_close"),
    path("archive/<int:order_id>/", views.archive_order, name="orders_archive"),
]
