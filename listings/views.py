from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Exists, OuterRef, Prefetch, Q
from django.shortcuts import get_object_or_404, render, redirect
from django.views import View
from django.views.decorators.http import require_POST

from inventory.models import InventoryProduct

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
                    filter=Q(variations__label__gt="", variations__is_deleted=False),
                    distinct=True,
                ),
                inventory_tracked=Exists(
                    InventoryProduct.objects.filter(
                        owner=request.user,
                        etsy_listing_id=OuterRef("etsy_listing_id"),
                        is_active=True,
                    )
                ),
            )
            .prefetch_related(
                Prefetch(
                    "variations",
                    queryset=ListingVariation.objects.filter(
                        label__gt="", is_deleted=False
                    ).order_by("id"),
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


@login_required
@require_POST
def set_inventory_tracking(request, listing_id):
    listing = get_object_or_404(Listing, pk=listing_id, owner=request.user)
    action = request.POST.get("action")

    if action == "track":
        product, _ = InventoryProduct.objects.get_or_create(
            owner=request.user,
            etsy_listing_id=listing.etsy_listing_id,
            defaults={"name": listing.title or str(listing.etsy_listing_id)},
        )
        if not product.is_active:
            product.is_active = True
            product.save(update_fields=["is_active"])
        if settings.INVENTORY_CATALOG_SYNC_ENABLED:
            messages.success(
                request,
                "Stok takibi açıldı. Varyasyonları güncellemek için Sync Now çalıştırın.",
            )
        else:
            messages.warning(
                request,
                "Stok takibi açıldı; varyasyon eşitlemesi için "
                "INVENTORY_CATALOG_SYNC_ENABLED=1 ayarını açın ve Sync Now çalıştırın.",
            )
    elif action == "untrack":
        InventoryProduct.objects.filter(
            owner=request.user, etsy_listing_id=listing.etsy_listing_id
        ).update(is_active=False)
        messages.success(request, "Stok takibi durduruldu; mevcut stok kayıtları korundu.")
    else:
        messages.error(request, "Geçersiz stok takibi işlemi.")

    return redirect("listings_home")
