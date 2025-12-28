from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.formats import date_format
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

STEP_STATE_LABELS = {
    "is-complete": "Tamamlandi",
    "is-active": "Islemde",
    "": "Beklemede",
}


def _format_detail_value(value, value_format=None):
    if value in (None, ""):
        return "-"
    if value_format and hasattr(value, "strftime"):
        return date_format(value, value_format)
    return value


def _decorate_details(details, active_label):
    for detail in details:
        if detail["label"] == "Durum":
            detail["display_label"] = "Aktif Durum"
            detail["display_value"] = active_label
            detail["is_status"] = True
        else:
            detail["display_label"] = detail["label"]
            detail["display_value"] = _format_detail_value(
                detail.get("value"), detail.get("value_format")
            )
            detail["is_status"] = False
    return details


def _build_step_details(order, shipment, status, step_state, active_label):
    if status == Order.Status.RECEIVED:
        dispatch_at = None
        if getattr(order, "expected_ship_date", None):
            dispatch_at = order.expected_ship_date

        details = [
            {
                "label": "Kargoya Verilmesi Gereken Tarih",
                "value": dispatch_at,
                "value_format": "d M Y",
            },
            {"label": "Yapilacaklar", "value": "Siparişi hazırla ve paketle"},
            {
                "label": "Durum",
                "value": Order.Status.RECEIVED,
            },
        ]
        return _decorate_details(details, active_label)

    details = [
        {"label": "Alan 1", "value": "Eklenecek"},
        {"label": "Alan 2", "value": "Eklenecek"},
        {"label": "Durum", "value": STEP_STATE_LABELS.get(step_state, "Beklemede")},
    ]
    return _decorate_details(details, active_label)


def _build_stepper(order, shipment):
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
        status = STATUS_STEPS[idx]["status"]
        if idx < active_index:
            step["state"] = "is-complete"
        elif idx == active_index:
            step["state"] = "is-active"
        else:
            step["state"] = ""

        if idx == active_index:
            step["details"] = _build_step_details(
                order, shipment, status, step["state"], step["label"]
            )

    active_step = steps[active_index] if steps else None
    return steps, progress, active_step


@login_required
def order_list(request):
    recent_cutoff = timezone.now() - timezone.timedelta(days=30)
    orders = (
        Order.objects.filter(
            owner=request.user,
            order_created_at__gte=recent_cutoff,
            archived=False,
        )
        .select_related("shipment")
        .prefetch_related("items")
        .order_by("-order_created_at", "-id")
    )
    cards = []
    for order in orders:
        items_count = len(order.items.all())
        try:
            shipment = order.shipment
        except Order.shipment.RelatedObjectDoesNotExist:
            shipment = None
        steps, progress, active_step = _build_stepper(order, shipment)

        if active_step:
            active_step["show_close_button"] = (
                order.status == Order.Status.DELIVERED
            )
            active_step["show_archive_button"] = (
                order.status == Order.Status.CLOSED
            )
            active_step["close_url"] = reverse("orders_close", args=[order.id])
            active_step["archive_url"] = reverse("orders_archive", args=[order.id])

        cards.append(
            {
                "order": order,
                "steps": steps,
                "progress": progress,
                "active_step": active_step,
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


@login_required
@require_POST
def archive_order(request, order_id):
    order = get_object_or_404(Order, id=order_id, owner=request.user)
    if order.status != Order.Status.CLOSED:
        messages.error(request, "Sadece kapatilan siparis arsive alinabilir.")
        return redirect("orders_home")
    if order.archived:
        messages.info(request, "Siparis zaten arsivde.")
        return redirect("orders_home")

    order.archived = True
    order.save(update_fields=["archived"])
    messages.success(request, "Siparis arsive alindi.")
    return redirect("orders_home")
