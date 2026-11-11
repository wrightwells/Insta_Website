from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from domain.content.models import SitePolicy
from web.public.policy import export_policy


class Command(BaseCommand):
    help = 'Publish the saved policy HTML for the isolated policy-only service.'

    def handle(self, *args, **options):
        if settings.RUNTIME != 'migration':
            raise CommandError('Policy export requires the operator migration runtime.')
        export_policy(SitePolicy.objects.get(pk=1))
        self.stdout.write('Saved policy exported.')
