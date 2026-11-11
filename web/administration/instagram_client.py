"""Bounded private agent calls. No SDK or Instagram session lives in Django."""
import io
import json
from pathlib import Path
from urllib.parse import urlsplit
import urllib.error
import urllib.request

from django.conf import settings
from django.utils.translation import gettext as _


class InstagramUnavailable(Exception):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class InstagramAgent:
    def __init__(self):
        self.url = settings.INSTAGRAM_AGENT_URL
        parsed = urlsplit(self.url)
        if (parsed.scheme != 'http' or parsed.hostname not in {'127.0.0.1', 'instagram-agent'}
                or parsed.username or parsed.password or parsed.path not in {'', '/'} or parsed.query or parsed.fragment):
            raise InstagramUnavailable(_("The Instagram service is not configured."))
        try:
            self.key = Path(settings.INSTAGRAM_CONTROL_KEY_FILE).read_text().strip()
        except OSError:
            raise InstagramUnavailable(_("The Instagram service is unavailable. Ask your operator to start it.")) from None
        if len(self.key) < 48:
            raise InstagramUnavailable(_("The Instagram service is not configured."))
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def call(self, operation, data=None, image=False):
        if operation not in {'status', 'account', 'connect', 'recent', 'image'}:
            raise ValueError('Unsupported operation')
        request = urllib.request.Request(self.url.rstrip('/') + '/v1/' + operation,
            data=json.dumps(data or {}).encode(), headers={'Authorization': 'Bearer ' + self.key,
                                                          'Content-Type': 'application/json'})
        limit = 10 * 1024 * 1024 if image else 1024 * 1024
        try:
            with self.opener.open(request, timeout=120 if operation in {'connect', 'image', 'recent'} else 10) as response:
                raw = response.read(limit + 1)
                if len(raw) > limit:
                    raise InstagramUnavailable(_("Instagram returned too much data. Try a smaller import."))
                return io.BytesIO(raw) if image else json.loads(raw)
        except urllib.error.HTTPError as exc:
            try:
                error = json.loads(exc.read(4096)).get('error', '')
            except (ValueError, TypeError, AttributeError):
                error = ''
            finally:
                exc.close()
            messages = {
                'two_factor_required': _("Enter a fresh two-factor code and connect again."),
                'challenge_required': _("Complete the account challenge directly in Instagram, then connect again."),
                'login_required': _("Your Instagram session expired. Connect again."),
                'login_rejected': _("Instagram rejected the login. Check your account details."),
                'not_connected': _("Connect your Instagram account first."),
                'not_configured': _("Save your Instagram account details first."),
                'wrong_account': _("Instagram returned a different account. Reconnect the intended account."),
                'rate_limited': _("Instagram requested a pause. Try again later."),
                'restricted': _("Instagram restricted this request. Check your account in Instagram."),
            }
            raise InstagramUnavailable(messages.get(error, _("The Instagram request failed. Existing website stories were retained."))) from None
        except (OSError, ValueError):
            raise InstagramUnavailable(_("The Instagram service could not be reached. Existing website stories were retained.")) from None
