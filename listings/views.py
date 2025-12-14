from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages

from .models import Listing
from .services import sync_active_listings

@login_required
def listings_home(request):
    if request.method == "POST":
        try:
            count = sync_active_listings(request.user)
            messages.success(request, f"Synced {count} active listings from Etsy.")
        except Exception as e:
            messages.error(request, f"Sync failed: {e}")
        return redirect("listings_home")

    qs = Listing.objects.filter(owner=request.user).order_by("-id")
    return render(request, "listings/home.html", {"listings": qs})
