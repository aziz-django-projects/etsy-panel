from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Prefetch, Q
from django.shortcuts import render, redirect
from django.views import View

from .models import Listing, ListingVariation
from .services import sync_active_listings

class ListingsHomeView(LoginRequiredMixin, View):
    template_name = "listings/home.html"

    def get(self, request):
        qs = (
            Listing.objects.filter(owner=request.user)
            .annotate(
                variation_count=Count(
                    "variations",
                    filter=Q(variations__label__gt=""),
                    distinct=True,
                )
            )
            .prefetch_related(
                Prefetch(
                    "variations",
                    queryset=ListingVariation.objects.filter(label__gt="").order_by("id"),
                    to_attr="visible_variations",
                )
            )
            .order_by("-id")
        )
        return render(request, self.template_name, {"listings": qs})

    def post(self, request):
        try:
            result = sync_active_listings(request.user)
            messages.success(
                request,
                (
                    f"Synced {result['listings_synced']} active listings from Etsy. "
                    f"Variation sync ok: {result['variation_sync_ok']}"
                ),
            )
            if result["variation_sync_failed"]:
                messages.warning(
                    request,
                    f"Variation sync failed for {result['variation_sync_failed']} listings. Check logs.",
                )
        except Exception as e:
            messages.error(request, f"Sync failed: {e}")
        return redirect("listings_home")
