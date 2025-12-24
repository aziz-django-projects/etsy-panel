from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from django.utils import timezone

from .models import Order
from .services import sync_orders

STATUS_STEPS = [
    {"status": Order.Status.RECEIVED, "label": "Siparis alindi", "icon": "check-lg"},
    {"status": Order.Status.SHIPPED, "label": "Kargoya verildi", "icon": "truck"},
    {"status": Order.Status.IN_TRANSIT, "label": "Yolda", "icon": "geo-alt"},
    {"status": Order.Status.DELIVERED, "label": "Teslim edildi", "icon": "flag"},
    {"status": Order.Status.CLOSED, "label": "Kapatildi", "icon": "x-circle"},
]

STATUS_LABELS = {step["status"]: step["label"] for step in STATUS_STEPS}


def _build_stepper(order):
    steps = [
        {key: value for key, value in step.items() if key != "status"}
        for step in STATUS_STEPS
    ]
    status_to_index = {
        step["status"]: index for index, step in enumerate(STATUS_STEPS)
    }
    active_index = status_to_index.get(order.status, 0)
    progress = int(active_index / (len(steps) - 1) * 100)

    for idx, step in enumerate(steps):
        if idx < active_index:
            step["state"] = "is-complete"
        elif idx == active_index:
            step["state"] = "is-active"
        else:
            step["state"] = ""

    return steps, progress


@login_required
def order_list(request):
    recent_cutoff = timezone.now() - timezone.timedelta(days=30)
    orders = (
        Order.objects.filter(owner=request.user, order_created_at__gte=recent_cutoff)
        .select_related("shipment")
        .prefetch_related("items")
        .order_by("-order_created_at", "-id")
    )
    cards = []
    for order in orders:
        steps, progress = _build_stepper(order)
        items_count = len(order.items.all())
        try:
            shipment = order.shipment
        except Order.shipment.RelatedObjectDoesNotExist:
            shipment = None

        cards.append(
            {
                "order": order,
                "steps": steps,
                "progress": progress,
                "items_count": items_count,
                "status_label": STATUS_LABELS.get(order.status, "Bilinmiyor"),
                "tracking_number": shipment.tracking_number if shipment else "",
                "carrier_name": shipment.carrier_name if shipment else "",
                "carrier_status": shipment.carrier_status if shipment else "",
            }
        )
    return render(request, "orders/home.html", {"order_cards": cards})


@login_required
@require_POST
def sync_now(request):
    try:
        total = sync_orders(request.user)
        messages.success(request, f"{total} siparis senkronize edildi.")
    except Exception as exc:
        messages.error(request, f"Siparis senkronu basarisiz: {exc}")
    return redirect("orders_home")


@login_required
@require_POST
def close_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, owner=request.user)
    if order.status != Order.Status.DELIVERED:
        messages.error(request, "Sadece teslim edilen siparis kapatilabilir.")
        return redirect("orders_home")

    order.status = Order.Status.CLOSED
    order.save(update_fields=["status"])
    messages.success(request, "Siparis kapatildi olarak isaretlendi.")
    return redirect("orders_home")
