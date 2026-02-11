from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Case, F, IntegerField, Prefetch, Value, When
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .models import InventoryProduct, StockBucket, StockMovement


@login_required
def inventory_home(request):
    products = (
        InventoryProduct.objects.filter(owner=request.user, is_active=True)
        .prefetch_related(
            Prefetch(
                "stock_buckets",
                queryset=StockBucket.objects.filter(is_active=True)
                .annotate(
                    size_order=Case(
                        When(name__endswith="-S", then=Value(0)),
                        When(name__endswith="-L", then=Value(1)),
                        default=Value(2),
                        output_field=IntegerField(),
                    )
                )
                .order_by("size_order", "name"),
            )
        )
        .order_by("name")
    )

    return render(
        request,
        "inventory/home.html",
        {
            "products": products,
        },
    )


@login_required
@require_POST
def adjust_bucket(request, bucket_id):
    bucket = get_object_or_404(
        StockBucket, id=bucket_id, owner=request.user, is_active=True
    )
    wants_json = request.headers.get("x-requested-with") == "XMLHttpRequest"
    try:
        delta = int(request.POST.get("delta", "0"))
    except (TypeError, ValueError):
        delta = 0

    if delta not in (-1, 1):
        if wants_json:
            return JsonResponse({"error": "invalid_delta"}, status=400)
        return redirect("inventory_home")

    if delta < 0 and bucket.quantity <= 0:
        if wants_json:
            return JsonResponse(
                {"error": "stock_zero", "quantity": bucket.quantity}, status=400
            )
        return redirect("inventory_home")

    with transaction.atomic():
        StockBucket.objects.filter(id=bucket.id).update(quantity=F("quantity") + delta)
        StockMovement.objects.create(
            owner=request.user,
            bucket=bucket,
            delta=delta,
            reason=StockMovement.Reason.MANUAL,
        )
        bucket.refresh_from_db(fields=["quantity"])

    if wants_json:
        return JsonResponse({"quantity": bucket.quantity})
    return redirect("inventory_home")
