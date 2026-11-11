import re

from django.core.exceptions import ImproperlyConfigured


def script_prefix(value):
    if value in {'', '/'}:
        return ''
    if not re.fullmatch(r'/[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*/?', value):
        raise ImproperlyConfigured('APP_SCRIPT_PREFIX must be an absolute path of simple segments, without query, fragment, escapes or dot segments.')
    return value.rstrip('/')
