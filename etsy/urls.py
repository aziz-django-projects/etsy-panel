from django.urls import path
from .views import callback, connect

urlpatterns = [
    path("connect/", connect, name="etsy_connect"),
    path("callback/", callback, name="etsy_callback"),
]
