from django.urls import path

from . import views

urlpatterns = [
    path("<int:pk>/", views.buyer_detail, name="buyer_detail"),
    path("<int:pk>/messages/", views.redirect_to_messages, name="buyer_messages"),
]

