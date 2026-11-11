from django.utils.translation import gettext_lazy as _
import uuid

from django.core.exceptions import ValidationError
from django.core.validators import MaxLengthValidator, MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.conf import settings

from .validators import validate_instagram_url


class Status(models.TextChoices):
    DRAFT = "draft", _("Draft")
    PUBLISHED = "published", _("Published")
    HIDDEN = "hidden", _("Hidden")
    ERROR = "error", _("Error")
    ARCHIVED = "archived", _("Archived")


class SourceAccount(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    platform = models.CharField(max_length=20, default="instagram")
    source_account_id = models.CharField(max_length=100)
    enabled = models.BooleanField(default=False)
    checkpoint = models.JSONField(default=dict)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["platform", "source_account_id"], name="source_account_identity")]


class PresentationItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(SourceAccount, on_delete=models.PROTECT)
    source_post_id = models.CharField(max_length=100)
    canonical_url = models.URLField(max_length=500, validators=[validate_instagram_url])
    source_published_at = models.DateTimeField()
    original_caption = models.TextField(blank=True)
    display_caption = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    publish_at = models.DateTimeField(null=True, blank=True)
    display_date = models.DateTimeField(null=True, blank=True)
    priority = models.IntegerField(default=0)
    version = models.PositiveIntegerField(default=1)
    deleted_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["account", "source_post_id"], name="source_post_identity"),
            models.CheckConstraint(condition=~models.Q(status="published") | models.Q(publish_at__isnull=False), name="published_has_date"),
            models.CheckConstraint(condition=models.Q(status__in=Status.values), name="item_valid_status"),
        ]
        indexes = [models.Index(fields=["status", "publish_at"], name="item_publication")]


class MediaAsset(models.Model):
    """Only validated, re-encoded PNG images are supported in this first increment."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item = models.ForeignKey(PresentationItem, on_delete=models.CASCADE, related_name="media")
    storage_key = models.CharField(max_length=40, unique=True, validators=[RegexValidator(r"\A[0-9a-f]{32}\.png\Z")])
    checksum = models.CharField(max_length=64)
    mime_type = models.CharField(max_length=50, default="image/png")
    size = models.PositiveIntegerField()
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    sequence = models.PositiveIntegerField(default=0)
    alt_en = models.CharField(max_length=500)
    alt_fr = models.CharField(max_length=500, blank=True)
    validated = models.BooleanField(default=False)
    active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["item", "sequence"], condition=models.Q(active=True), name="active_media_sequence")]


class SiteCopy(models.Model):
    """Public copy only. Contact recipients and secrets must never be added here."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    name = models.CharField(max_length=100, default="Fieldnotes")
    journal_en = models.CharField(max_length=100, blank=True, default="")
    journal_fr = models.CharField(max_length=100, blank=True, default="")
    feed_heading_en = models.CharField(max_length=200, blank=True, default="")
    feed_heading_fr = models.CharField(max_length=200, blank=True, default="")
    intro_en = models.TextField(default="A collection of moments, stories and discoveries.")
    intro_fr = models.TextField(default="Une collection de moments, de récits et de découvertes.")
    footer_en = models.TextField(default="Thanks for stopping by.")
    footer_fr = models.TextField(default="Merci de votre visite.")
    empty_en = models.TextField(default="New stories are on their way. Check back soon.")
    empty_fr = models.TextField(default="De nouvelles histoires arrivent. À bientôt.")
    default_locale = models.CharField(max_length=2, choices=[("en", _("English")), ("fr", _("Français"))], default="en")
    english_enabled = models.BooleanField(default=True)
    french_enabled = models.BooleanField(default=True)
    page_size = models.PositiveSmallIntegerField(default=12, validators=[MinValueValidator(1), MaxValueValidator(48)])

    contact_email = models.EmailField(blank=True, default="email@site.eu")
    contact_phone = models.CharField(max_length=60, blank=True, default="")
    contact_address = models.TextField(blank=True, default="")
    contact_intro_en = models.TextField(blank=True, default="")
    contact_intro_fr = models.TextField(blank=True, default="")
    contact_hours_en = models.TextField(blank=True, default="")
    contact_hours_fr = models.TextField(blank=True, default="")
    reviews_enabled = models.BooleanField(default=True)

    seo_feed_title_en = models.CharField(max_length=160, blank=True, default="")
    seo_feed_title_fr = models.CharField(max_length=160, blank=True, default="")
    seo_feed_description_en = models.CharField(max_length=320, blank=True, default="")
    seo_feed_description_fr = models.CharField(max_length=320, blank=True, default="")
    seo_reviews_title_en = models.CharField(max_length=160, blank=True, default="")
    seo_reviews_title_fr = models.CharField(max_length=160, blank=True, default="")
    seo_reviews_description_en = models.CharField(max_length=320, blank=True, default="")
    seo_reviews_description_fr = models.CharField(max_length=320, blank=True, default="")
    seo_contact_title_en = models.CharField(max_length=160, blank=True, default="")
    seo_contact_title_fr = models.CharField(max_length=160, blank=True, default="")
    seo_contact_description_en = models.CharField(max_length=320, blank=True, default="")
    seo_contact_description_fr = models.CharField(max_length=320, blank=True, default="")

    seo_public_origin = models.CharField(max_length=500, blank=True, default="")
    seo_home_canonical_en = models.CharField(max_length=500, blank=True, default="")
    seo_home_canonical_fr = models.CharField(max_length=500, blank=True, default="")
    seo_robots = models.CharField(max_length=10, default="inherit", choices=[("inherit", _("Deployment default")), ("index", _("Index and follow")), ("noindex", _("Do not index; follow links"))])
    seo_max_image_preview = models.CharField(max_length=8, blank=True, default="", choices=[("", _("Default")), ("large", _("Large")), ("standard", _("Standard")), ("none", _("None"))])
    seo_social_site_name = models.CharField(max_length=100, blank=True, default="")
    seo_og_type = models.CharField(max_length=12, default="website", choices=[("website", "website"), ("article", "article"), ("profile", "profile")])
    seo_social_image = models.CharField(max_length=500, blank=True, default="")
    seo_image_width = models.PositiveIntegerField(default=1200, validators=[MinValueValidator(1), MaxValueValidator(10000)])
    seo_image_height = models.PositiveIntegerField(default=630, validators=[MinValueValidator(1), MaxValueValidator(10000)])
    seo_locale_en = models.CharField(max_length=5, default="en_GB")
    seo_locale_fr = models.CharField(max_length=5, default="fr_FR")
    seo_twitter_card = models.CharField(max_length=20, default="auto", choices=[("auto", _("Automatic")), ("summary", "summary"), ("summary_large_image", "summary_large_image")])
    seo_twitter_image = models.CharField(max_length=500, blank=True, default="")
    seo_favicon = models.CharField(max_length=500, blank=True, default="")
    seo_apple_icon = models.CharField(max_length=500, blank=True, default="")
    seo_theme_color = models.CharField(max_length=7, blank=True, default="")
    seo_google_verification = models.CharField(max_length=200, blank=True, default="")
    seo_bing_verification = models.CharField(max_length=200, blank=True, default="")
    seo_business_enabled = models.BooleanField(default=False)
    seo_business_type = models.CharField(max_length=40, default="HomeAndConstructionBusiness", choices=[("HomeAndConstructionBusiness", "HomeAndConstructionBusiness"), ("LocalBusiness", "LocalBusiness")])
    seo_business_id = models.CharField(max_length=500, blank=True, default="")
    seo_business_name = models.CharField(max_length=150, blank=True, default="")
    seo_business_url = models.CharField(max_length=500, blank=True, default="")
    seo_business_image = models.CharField(max_length=500, blank=True, default="")
    seo_business_price_range = models.CharField(max_length=30, blank=True, default="")
    seo_business_street = models.CharField(max_length=200, blank=True, default="")
    seo_business_town = models.CharField(max_length=100, blank=True, default="")
    seo_business_postcode = models.CharField(max_length=30, blank=True, default="")
    seo_business_country = models.CharField(max_length=2, default="GB")
    seo_business_area_served = models.CharField(max_length=100, blank=True, default="")
    seo_og_title_en = models.CharField(max_length=160, blank=True, default="")
    seo_og_title_fr = models.CharField(max_length=160, blank=True, default="")
    seo_og_description_en = models.CharField(max_length=320, blank=True, default="")
    seo_og_description_fr = models.CharField(max_length=320, blank=True, default="")
    seo_og_url_en = models.CharField(max_length=500, blank=True, default="")
    seo_og_url_fr = models.CharField(max_length=500, blank=True, default="")
    seo_image_alt_en = models.CharField(max_length=500, blank=True, default="")
    seo_image_alt_fr = models.CharField(max_length=500, blank=True, default="")
    seo_twitter_title_en = models.CharField(max_length=160, blank=True, default="")
    seo_twitter_title_fr = models.CharField(max_length=160, blank=True, default="")
    seo_twitter_description_en = models.CharField(max_length=320, blank=True, default="")
    seo_twitter_description_fr = models.CharField(max_length=320, blank=True, default="")
    seo_business_description_en = models.CharField(max_length=500, blank=True, default="")
    seo_business_description_fr = models.CharField(max_length=500, blank=True, default="")

    def clean(self):
        from .discovery import validate_discovery
        validate_discovery(self)
        if not {"en": self.english_enabled, "fr": self.french_enabled}.get(self.default_locale):
            raise ValidationError(_("The default language must be enabled."))

    class Meta:
        abstract = True


class SiteContent(SiteCopy):
    version = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(id=1), name="single_site_content"),
            models.CheckConstraint(condition=models.Q(page_size__gte=1, page_size__lte=48), name="bounded_page_size"),
            models.CheckConstraint(condition=(models.Q(default_locale="en", english_enabled=True) | models.Q(default_locale="fr", french_enabled=True)), name="enabled_default_locale"),
        ]


class Review(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    reviewer_name = models.CharField(max_length=100)
    text_en = models.TextField(blank=True)
    text_fr = models.TextField(blank=True)
    rating = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)])
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    published_at = models.DateTimeField(null=True, blank=True)
    priority = models.IntegerField(default=0)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=~models.Q(text_en="") | ~models.Q(text_fr=""), name="review_has_text"),
            models.CheckConstraint(condition=models.Q(rating__isnull=True) | models.Q(rating__gte=1, rating__lte=5), name="review_rating_range"),
            models.CheckConstraint(condition=~models.Q(status="published") | models.Q(published_at__isnull=False), name="review_published_has_date"),
            models.CheckConstraint(condition=models.Q(status__in=Status.values), name="review_valid_status"),
        ]


# Read models target database views rather than the private tables. Runtime role
# grants protect the boundary even if a future view accidentally omits a filter.
class PublicItem(models.Model):
    id = models.UUIDField(primary_key=True)
    canonical_url = models.URLField()
    caption = models.TextField()
    effective_date = models.DateTimeField()
    source_published_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "public_feed"


class PublicMedia(models.Model):
    id = models.UUIDField(primary_key=True)
    item_id = models.UUIDField()
    storage_key = models.CharField(max_length=40)
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    alt_en = models.CharField(max_length=500)
    alt_fr = models.CharField(max_length=500)
    sequence = models.PositiveIntegerField()

    class Meta:
        managed = False
        db_table = "public_media"


class PublicSiteContent(SiteCopy):
    class Meta:
        managed = False
        db_table = "public_site_content"


class PublicReview(models.Model):
    id = models.UUIDField(primary_key=True)
    reviewer_name = models.CharField(max_length=100)
    text_en = models.TextField()
    text_fr = models.TextField()
    rating = models.PositiveSmallIntegerField(null=True)
    published_at = models.DateTimeField()
    priority = models.IntegerField()

    class Meta:
        managed = False
        db_table = "public_reviews"


class SiteOwner(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(id=1), name="single_site_owner")]


class LoginCounter(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    window_started = models.DateTimeField()
    attempts = models.PositiveIntegerField(default=0)


class ContentRevision(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    entity = models.CharField(max_length=30)
    entity_id = models.CharField(max_length=40)
    version = models.PositiveIntegerField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    snapshot = models.JSONField()


class AuditEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    action = models.CharField(max_length=40)
    entity = models.CharField(max_length=30)
    entity_id = models.CharField(max_length=40)
    changed_fields = models.JSONField(default=list)
    revision = models.ForeignKey(ContentRevision, on_delete=models.PROTECT, null=True)


class MediaQuota(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    bytes_used = models.PositiveBigIntegerField(default=0)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(id=1), name="single_media_quota")]


class ThemeImage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    storage_key = models.CharField(max_length=40, unique=True, validators=[RegexValidator(r"\A[0-9a-f]{32}\.png\Z")])
    checksum = models.CharField(max_length=64)
    mime_type = models.CharField(max_length=50, default="image/png")
    size = models.PositiveIntegerField()
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()
    validated = models.BooleanField(default=False)


class ThemeValues(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    background_color = models.CharField(max_length=7, default="#f8f6f0")
    text_color = models.CharField(max_length=7, default="#253b33")
    muted_color = models.CharField(max_length=7, default="#52665d")
    accent_color = models.CharField(max_length=7, default="#9e4934")
    font = models.CharField(max_length=12, choices=[("editorial", _("Editorial")), ("system", _("System sans-serif")), ("serif", _("Serif"))], default="editorial")

    def clean(self):
        from .theme import validate_theme
        validate_theme(self)

    class Meta:
        abstract = True


class SiteTheme(ThemeValues):
    version = models.PositiveIntegerField(default=1)
    background_image = models.ForeignKey(ThemeImage, null=True, blank=True, on_delete=models.PROTECT)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(id=1), name="single_site_theme")]


class PublicTheme(ThemeValues):
    background_image_id = models.UUIDField(null=True)

    class Meta:
        managed = False
        db_table = "public_theme"


class PublicThemeImage(models.Model):
    id = models.UUIDField(primary_key=True)
    storage_key = models.CharField(max_length=40)

    class Meta:
        managed = False
        db_table = "public_theme_image"


class InstagramImport(models.Model):
    """Source snapshot and importer-owned media identity; no credentials or CDN URLs."""
    item = models.OneToOneField(PresentationItem, primary_key=True, on_delete=models.CASCADE)
    source_snapshot = models.JSONField(default=dict)
    media_ids = models.JSONField(default=list)
    imported_at = models.DateTimeField(auto_now=True)


class InstagramSync(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    lease = models.UUIDField(null=True)
    running_until = models.DateTimeField(null=True)
    last_finished_at = models.DateTimeField(null=True)
    summary = models.JSONField(default=dict)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(id=1), name="single_instagram_sync")]


class ContactRate(models.Model):
    key = models.CharField(max_length=64, primary_key=True)
    window_started = models.DateTimeField()
    attempts = models.PositiveIntegerField(default=0)


class ContactDelivery(models.Model):
    """Delivery state only: email addresses, phone numbers and messages are not stored."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    state = models.CharField(max_length=10, default='new')


from .policy import DEFAULT_POLICY_BODY, default_policy_date


class PolicyCopy(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    title = models.CharField(max_length=200, default="Privacy policy")
    site_name = models.CharField(max_length=100, default="MySite")
    operator_name = models.CharField(max_length=150, blank=True, default="")
    contact_address = models.TextField(blank=True, default="")
    updated_on = models.DateField(default=default_policy_date)
    body = models.TextField(default=DEFAULT_POLICY_BODY, validators=[MaxLengthValidator(50000)])

    class Meta:
        abstract = True


class SitePolicy(PolicyCopy):
    version = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(id=1), name="single_site_policy")]


class PublicPolicy(PolicyCopy):
    contact_email = models.EmailField(blank=True)

    class Meta:
        managed = False
        db_table = "public_policy"
