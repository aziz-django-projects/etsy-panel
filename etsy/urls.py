from django.urls import path
from .views import callback, connect

urlpatterns = [
    path("connect/", connect, name="etsy_connect"),
    path("callback/", callback, name="etsy_callback"),
    # Etsy bazen trailing slash olmadan dönebildiği için 301'den kaçın.
    path("callback", callback),
]
