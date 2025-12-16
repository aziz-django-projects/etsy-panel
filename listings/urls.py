from django.urls import path
from .views import ListingsHomeView

urlpatterns = [
    path("", ListingsHomeView.as_view(), name="listings_home"),
]
