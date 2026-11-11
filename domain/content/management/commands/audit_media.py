import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, connection, transaction

from domain.content.storage_audit import audit_media


class Command(BaseCommand):
    help = "Report private media references, file integrity and quota discrepancies without changing data."
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument("--verify", action="store_true", help="Stream and verify registered PNG file checksums.")
        parser.add_argument("--check", action="store_true", help="Exit unsuccessfully after reporting any discrepancy.")

    def handle(self, *args, **options):
        if settings.RUNTIME != "migration":
            raise CommandError("Media audits require APP_RUNTIME=migration and the operator database identity.")
        try:
            with transaction.atomic():
                if connection.vendor == "postgresql":
                    with connection.cursor() as cursor:
                        cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                report = audit_media(verify=options["verify"])
        except DatabaseError as exc:
            raise CommandError("Media audit could not read a consistent database snapshot. No changes were made.") from exc
        self.stdout.write(json.dumps(report, ensure_ascii=True, sort_keys=True, indent=2))
        if options["check"] and not report["ok"]:
            raise CommandError("Media audit found discrepancies. Review the JSON report; no files or accounting were changed.")
