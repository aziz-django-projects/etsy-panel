from urllib.parse import urlencode, urlparse

import httpx
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.utils import timezone
from django.http import HttpResponseBadRequest

from .models import EtsyAccount
from .pkce import generate_code_verifier, generate_code_challenge, generate_state


AUTHORIZE_URL = "https://www.etsy.com/oauth/connect"
TOKEN_URL = "https://api.etsy.com/v3/public/oauth/token"  # Etsy dokümanı :contentReference[oaicite:3]{index=3}

@login_required
def connect(request):
    redirect_uri = settings.ETSY_REDIRECT_URI
    redirect_parts = urlparse(redirect_uri) if redirect_uri else None
    if redirect_parts and redirect_parts.netloc:
        current_host = request.get_host()
        if current_host != redirect_parts.netloc:
            return redirect(f"{redirect_parts.scheme}://{redirect_parts.netloc}{request.get_full_path()}")

    verifier = generate_code_verifier()
    challenge = generate_code_challenge(verifier)
    state = generate_state()

    # Session'da sakla. Tek state yerine birden fazla denemeyi destekle (prefetch/double-click vb.).
    states = request.session.get("etsy_oauth_states") or {}
    states[state] = verifier
    if len(states) > 5:
        for old_state in list(states.keys())[:-5]:
            states.pop(old_state, None)
    request.session["etsy_oauth_states"] = states

    params = {
        "response_type": "code",
        "client_id": settings.ETSY_CLIENT_ID,
        "redirect_uri": settings.ETSY_REDIRECT_URI,
        "scope": settings.ETSY_SCOPES,  # space-separated
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return redirect(f"{AUTHORIZE_URL}?{urlencode(params)}")


@login_required
def callback(request):
    # Etsy, redirect_uri’ye code + state ile döner :contentReference[oaicite:4]{index=4}
    code = request.GET.get("code")
    state = request.GET.get("state")
    if not code or not state:
        return HttpResponseBadRequest("Missing code/state")

    states = request.session.get("etsy_oauth_states") or {}
    verifier = states.get(state)
    if not verifier:
        return HttpResponseBadRequest("Invalid state (CSRF)")

    # State'i tek kullanimlik yap
    states.pop(state, None)
    request.session["etsy_oauth_states"] = states

    data = {
        "grant_type": "authorization_code",
        "client_id": settings.ETSY_CLIENT_ID,
        "redirect_uri": settings.ETSY_REDIRECT_URI,
        "code": code,
        "code_verifier": verifier,
    }

    # Etsy token endpoint: form-encoded POST :contentReference[oaicite:5]{index=5}
    with httpx.Client(timeout=20) as client:
        resp = client.post(TOKEN_URL, data=data)
        resp.raise_for_status()
        payload = resp.json()

    access_token = payload["access_token"]
    refresh_token = payload.get("refresh_token", "")
    expires_in = int(payload.get("expires_in", 3600))

    # Etsy access_token formatında numeric user_id prefix var (12345678.xxx) :contentReference[oaicite:6]{index=6}
    etsy_user_id = None
    if "." in access_token:
        maybe_prefix = access_token.split(".", 1)[0]
        if maybe_prefix.isdigit():
            etsy_user_id = int(maybe_prefix)

    account, _ = EtsyAccount.objects.get_or_create(user=request.user)
    account.etsy_user_id = etsy_user_id
    account.access_token = access_token
    account.refresh_token = refresh_token
    account.expires_at = timezone.now() + timezone.timedelta(seconds=expires_in)
    account.scopes = settings.ETSY_SCOPES
    account.last_connected_at = timezone.now()
    account.save()

    return redirect("listings_home")

