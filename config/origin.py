from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.validators import URLValidator


def public_origin(value, *, local):
    if not value:
        return ""
    try:
        parsed = urlsplit(value)
        URLValidator(schemes=["https", "http"] if local else ["https"])(value)
        if value != value.strip() or any(char.isspace() for char in value) or parsed.username is not None or parsed.password is not None or parsed.path not in {"", "/"} or "?" in value or "#" in value:
            raise ValueError
        parsed.port  # Validate malformed port numbers before normalizing.
    except (ValidationError, ValueError) as exc:
        raise ImproperlyConfigured("PUBLIC_ORIGIN must be an absolute HTTPS origin without credentials, path, query or fragment (HTTP is allowed locally).") from exc
    return value.rstrip("/")
