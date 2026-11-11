from getpass import getpass

from django.conf import settings
from django.contrib.auth import get_user_model, password_validation
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from domain.content.models import AuditEvent, SiteContent, SiteOwner


class Command(BaseCommand):
    help = "Provision the single named owner interactively using the migration identity."

    def add_arguments(self, parser):
        parser.add_argument("username")

    @transaction.atomic
    def handle(self, *args, **options):
        if settings.RUNTIME != "migration":
            raise CommandError("Owner provisioning requires APP_RUNTIME=migration.")
        if SiteOwner.objects.exists():
            raise CommandError("An owner already exists. Use the operator recovery procedure.")
        user = get_user_model()(username=options["username"], is_active=True, is_staff=True, is_superuser=False)
        password = getpass("Owner password: ")
        if password != getpass("Confirm password: "):
            raise CommandError("Passwords did not match.")
        try:
            password_validation.validate_password(password, user)
            user.set_password(password)
            user.full_clean()
        except ValidationError as exc:
            raise CommandError("; ".join(exc.messages)) from exc
        user.save()
        SiteOwner.objects.create(user=user)
        SiteContent.objects.get_or_create(pk=1)
        AuditEvent.objects.create(actor=user, action="provision", entity="owner", entity_id=str(user.pk))
        self.stdout.write(self.style.SUCCESS("Named owner provisioned. No password is displayed or exported."))
