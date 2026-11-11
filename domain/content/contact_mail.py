"""Private SMTP configuration and bounded, idempotent contact delivery."""
import fcntl
import json
import os
import smtplib
import tempfile
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.mail import EmailMessage, get_connection
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac

from .editing import EditConflict, require_owner
from .models import AuditEvent, ContactDelivery, ContactRate

DEFAULTS = dict(version=1, enabled=False, host='', port=587, security='starttls', username='', password='', from_email='')


class DeliveryUnavailable(Exception):
    pass


class ContactLimited(Exception):
    pass


def read_mail_settings():
    path = Path(settings.CONTACT_MAIL_SETTINGS_FILE)
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return DEFAULTS.copy()
    with os.fdopen(fd) as handle:
        record = json.load(handle)
    if not isinstance(record, dict) or set(record) != set(DEFAULTS):
        raise ValueError('Invalid mail configuration')
    return record


def _write_settings(path, record):
    fd, temporary = tempfile.mkstemp(prefix='.smtp-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as handle:
            json.dump(record, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def save_mail_settings(*, actor, values):
    require_owner(actor)
    path = Path(settings.CONTACT_MAIL_SETTINGS_FILE)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    lock_fd = os.open(path.with_suffix('.lock'), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(lock_fd, 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        previous = read_mail_settings()
        if previous['version'] != values['version']:
            raise EditConflict
        password = '' if values.get('clear_password') else values.get('password') or previous['password']
        record = {name: values[name] for name in DEFAULTS if name not in ('password', 'version')}
        record.update(password=password, version=previous['version']+1)
        changed = sorted(name for name in record if name != 'version' and record[name] != previous[name])
        try:
            with transaction.atomic():
                AuditEvent.objects.create(actor=actor, action='edit_contact_mail', entity='contact_mail',
                    entity_id='1', changed_fields=changed)
                _write_settings(path, record)
        except Exception:
            _write_settings(path, previous)
            raise
        return record


def mail_ready(config, recipient):
    return bool(config['enabled'] and config['host'] and config['from_email'] and recipient and recipient.casefold() != 'email@site.eu'
        and (not config['username'] or config['password']))


def reserve_contact(address, delivery_id):
    with transaction.atomic():
        key = salted_hmac('contact-rate-v1', address, algorithm='sha256').hexdigest()
        now = timezone.now()
        counter, _created = ContactRate.objects.select_for_update().get_or_create(key=key,
            defaults={'window_started': now})
        if counter.window_started <= now-timedelta(minutes=15):
            counter.window_started, counter.attempts = now, 0
        delivery, created = ContactDelivery.objects.select_for_update().get_or_create(pk=delivery_id)
        if not created:
            if delivery.state == 'sent':
                return False
            if delivery.state == 'sending':
                raise DeliveryUnavailable
        if counter.attempts >= 5:
            raise ContactLimited
        counter.attempts += 1
        counter.save(update_fields=['window_started', 'attempts'])
        delivery.state = 'sending'
        delivery.save(update_fields=['state'])
    return True


def deliver_contact(*, recipient, email, mobile, message, address, delivery_id):
    try:
        config = read_mail_settings()
    except (OSError, ValueError):
        raise DeliveryUnavailable from None
    if not mail_ready(config, recipient):
        raise DeliveryUnavailable
    if not reserve_contact(address, delivery_id):
        return
    try:
        connection = get_connection(backend=settings.CONTACT_EMAIL_BACKEND, host=config['host'], port=config['port'],
            username=config['username'], password=config['password'], use_tls=config['security']=='starttls',
            use_ssl=config['security']=='ssl', timeout=15, fail_silently=False)
        mail = EmailMessage(subject='Website contact enquiry',
            body=f'Email: {email}\nMobile: {mobile}\n\n{message}',
            from_email=config['from_email'], to=[recipient], reply_to=[email], connection=connection)
        if mail.send() != 1:
            raise DeliveryUnavailable
    except (OSError, ValueError, smtplib.SMTPException, DeliveryUnavailable):
        ContactDelivery.objects.filter(pk=delivery_id).update(state='failed')
        raise DeliveryUnavailable from None
    ContactDelivery.objects.filter(pk=delivery_id).update(state='sent')
