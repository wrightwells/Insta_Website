from django.utils.translation import gettext_lazy as _
import re
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError


def validate_instagram_url(value: str) -> None:
    try:
        url = urlsplit(value)
        valid = (
            url.scheme == "https" and url.netloc == "www.instagram.com"
            and not url.query and not url.fragment
            and re.fullmatch(r"/(p|reel|tv)/[A-Za-z0-9_-]+/", url.path)
        )
    except ValueError:
        valid = False
    if not valid:
        raise ValidationError(_("Use a canonical HTTPS Instagram post URL without query parameters."))
