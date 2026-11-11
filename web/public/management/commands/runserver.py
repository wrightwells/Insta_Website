from django.conf import settings
from django.contrib.staticfiles.management.commands.runserver import Command as StaticRunserver


class Command(StaticRunserver):
    def check_migrations(self):
        # The public PostgreSQL login deliberately cannot read django_migrations.
        # An explicit migration process owns readiness/schema verification.
        if settings.RUNTIME != "migration":
            return
        return super().check_migrations()
