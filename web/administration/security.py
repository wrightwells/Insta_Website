import math
import unicodedata
from datetime import timedelta

from django.contrib.auth import logout
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac

from domain.content.models import LoginCounter, SiteOwner

WINDOW_SECONDS = 15 * 60


def counter_key(scope: str, value: str) -> str:
    if scope == "account":
        value = unicodedata.normalize("NFKC", value).strip().casefold()[:150]
    return salted_hmac("admin-login-v1", f"{scope}:{value}", algorithm="sha256").hexdigest()


@transaction.atomic
def reserve_login(username: str, address: str) -> int:
    """Reserve attempts before expensive authentication to bound concurrent abuse.

    Fixed windows are shared across workers. Successful login clears the account
    bucket; the IP cap counts all attempts. No raw usernames or IPs are stored.
    """
    now = timezone.now()
    limits = {counter_key("account", username): 5, counter_key("ip", address): 20}
    counters = []
    retry_after = 0
    for key, limit in sorted(limits.items()):
        counter, _ = LoginCounter.objects.select_for_update().get_or_create(key=key, defaults={"window_started": now})
        if counter.window_started <= now - timedelta(seconds=WINDOW_SECONDS):
            counter.window_started, counter.attempts = now, 0
        counters.append(counter)
        if counter.attempts >= limit:
            retry_after = max(retry_after, math.ceil(WINDOW_SECONDS - (now - counter.window_started).total_seconds()))
    if retry_after:
        return retry_after
    for counter in counters:
        counter.attempts += 1
        counter.save(update_fields=["window_started", "attempts"])
    return 0


class OwnerSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        now = timezone.now().timestamp()
        if request.user.is_authenticated:
            started = request.session.get("owner_login_at")
            seen = request.session.get("owner_seen_at")
            valid = (
                isinstance(started, (int, float)) and isinstance(seen, (int, float))
                and 0 <= now - started < 12 * 3600 and 0 <= now - seen < 1800
                and request.user.is_staff
                and SiteOwner.objects.filter(pk=1, user_id=request.user.pk).exists()
            )
            if not valid:
                logout(request)
            else:
                request.session["owner_seen_at"] = now
        elif request.session.get("_auth_user_id"):
            # Disabled/deleted accounts no longer authenticate; revoke this copy.
            logout(request)
        return self.get_response(request)
