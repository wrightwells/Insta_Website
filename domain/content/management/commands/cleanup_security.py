from datetime import timedelta

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from domain.content.models import LoginCounter, ContactRate, ContactDelivery


class Command(BaseCommand):
    help = "Expire pseudonymous login counters and expired Django sessions."

    def handle(self, *args, **options):
        if settings.RUNTIME != "migration":
            raise CommandError("Cleanup requires the operator migration runtime.")
        LoginCounter.objects.filter(window_started__lt=timezone.now() - timedelta(minutes=15)).delete()
        ContactRate.objects.filter(window_started__lt=timezone.now()-timedelta(minutes=15)).delete()
        ContactDelivery.objects.filter(created_at__lt=timezone.now()-timedelta(days=7)).delete()
        call_command("clearsessions")
        self.stdout.write("Expired security state removed.")
