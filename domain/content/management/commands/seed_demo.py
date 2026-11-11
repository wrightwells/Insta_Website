import io
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from PIL import Image, ImageDraw

from domain.content.media import stage_image
from domain.content.models import PresentationItem, SiteContent, SourceAccount, Status


class Command(BaseCommand):
    help = "Create three clearly labelled synthetic posts in local development only."

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.LOCAL or settings.RUNTIME not in {"migration", "admin"}:
            raise CommandError("Use APP_LOCAL=1 APP_RUNTIME=migration with a disposable development database.")
        SiteContent.objects.get_or_create(pk=1)
        account, _ = SourceAccount.objects.get_or_create(source_account_id="synthetic-demo", defaults={"enabled": False})
        for index, colour in enumerate(("#cfa582", "#8eaa9a", "#b5bacb"), start=1):
            item, created = PresentationItem.objects.get_or_create(
                account=account, source_post_id=f"demo{index}", defaults={
                    "canonical_url": f"https://www.instagram.com/p/SYNTHETIC_DEMO_{index}/",
                    "source_published_at": timezone.now() - timedelta(days=index),
                    "original_caption": f"Synthetic development story {index}.\n\nThis is test content, not an imported Instagram post.",
                },
            )
            if not created:
                continue
            image = Image.new("RGB", (960, 720), colour)
            draw = ImageDraw.Draw(image)
            draw.ellipse((280, 100, 680, 500), fill="#f8f6f0")
            draw.rectangle((0, 440, 960, 720), fill="#253b33")
            draw.text((36, 660), "SYNTHETIC DEVELOPMENT IMAGE", fill="#ffffff", font_size=28)
            stream = io.BytesIO()
            image.save(stream, "PNG")
            stream.seek(0)
            stage_image(item, stream, alt_en="Synthetic geometric landscape for development", alt_fr="Paysage géométrique synthétique de démonstration")
            item.status = Status.PUBLISHED
            item.publish_at = timezone.now() - timedelta(minutes=1)
            item.full_clean()
            item.save()
        self.stdout.write(self.style.SUCCESS("Synthetic demo ready. No Instagram requests or credentials were used."))
