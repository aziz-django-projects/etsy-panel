from datetime import timedelta

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from listings.models import Listing
from orders.models import Order


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["low_stock"] = Listing.objects.filter(
            owner=self.request.user,
            quantity__lt=3,
        ).order_by("quantity", "-id")
        stale_orders = []
        orders = (
            Order.objects.filter(
                owner=self.request.user,
                status__in=[Order.Status.SHIPPED, Order.Status.IN_TRANSIT],
                order_created_at__isnull=False,
                shipment__last_activity_at__isnull=False,
            )
            .select_related("shipment")
            .order_by("-order_created_at")
        )
        for order in orders:
            gap = order.shipment.last_activity_at - order.order_created_at
            if gap >= timedelta(days=15):
                stale_orders.append(
                    {
                        "order": order,
                        "gap_days": gap.days,
                    }
                )
        stale_orders.sort(key=lambda item: item["gap_days"], reverse=True)
        context["stale_orders"] = stale_orders
        return context
