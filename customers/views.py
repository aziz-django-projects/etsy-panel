from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, render

from .models import Buyer


@login_required
def buyer_detail(request, pk: int):
    buyer = get_object_or_404(Buyer, pk=pk, owner=request.user)
    return render(request, "customers/detail.html", {"buyer": buyer})


@login_required
def redirect_to_messages(request, pk: int):
    buyer = get_object_or_404(Buyer, pk=pk, owner=request.user)
    return HttpResponseRedirect(buyer.etsy_messages_url)

