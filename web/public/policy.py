"""Publish a rendered policy artifact for the isolated policy-only service."""
import os
import tempfile
from pathlib import Path

from django.conf import settings
from django.template.loader import render_to_string
from django.utils import translation

from domain.content.policy import policy_context


def write_policy_file(path, contents):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.policy-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(contents)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def export_policy(policy):
    path = Path(settings.POLICY_EXPORT_FILE)
    previous = path.read_bytes() if path.exists() else None
    from domain.content.models import SiteContent
    from domain.content.policy import DEFAULT_POLICY_EMAIL
    site = SiteContent.objects.first()
    email = site.contact_email if site is not None else DEFAULT_POLICY_EMAIL
    with translation.override('en'):
        contents = render_to_string('public/privacy.html', policy_context(policy, contact_email=email)).encode('utf-8')
    write_policy_file(path, contents)
    return path, previous


def restore_export(backup):
    path, previous = backup
    if previous is None:
        path.unlink(missing_ok=True)
    else:
        write_policy_file(path, previous)
