from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import render, redirect
from django.views import View

from .models import Listing
from .services import sync_active_listings

class ListingsHomeView(LoginRequiredMixin, View):
    template_name = "listings/home.html"

    def get(self, request):
        qs = Listing.objects.filter(owner=request.user).order_by("-id")
        return render(request, self.template_name, {"listings": qs})

    def post(self, request):
        try:
            count = sync_active_listings(request.user)
            messages.success(request, f"Synced {count} active listings from Etsy.")
        except Exception as e:
            messages.error(request, f"Sync failed: {e}")
        return redirect("listings_home")
