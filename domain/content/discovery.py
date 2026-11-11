"""Typed site discovery settings; no arbitrary head markup or script input."""
import re
from urllib.parse import urlsplit

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.utils.translation import gettext_lazy as _

DISCOVERY_FIELDS = (
    'seo_public_origin', 'seo_home_canonical_en', 'seo_home_canonical_fr',
    'seo_robots', 'seo_max_image_preview', 'seo_social_site_name', 'seo_og_type',
    'seo_og_title_en', 'seo_og_title_fr', 'seo_og_description_en', 'seo_og_description_fr',
    'seo_og_url_en', 'seo_og_url_fr', 'seo_social_image', 'seo_image_width', 'seo_image_height',
    'seo_image_alt_en', 'seo_image_alt_fr', 'seo_locale_en', 'seo_locale_fr',
    'seo_twitter_card', 'seo_twitter_title_en', 'seo_twitter_title_fr',
    'seo_twitter_description_en', 'seo_twitter_description_fr', 'seo_twitter_image',
    'seo_favicon', 'seo_apple_icon', 'seo_theme_color', 'seo_google_verification', 'seo_bing_verification',
    'seo_business_enabled', 'seo_business_type', 'seo_business_id', 'seo_business_name',
    'seo_business_url', 'seo_business_image', 'seo_business_description_en', 'seo_business_description_fr',
    'seo_business_price_range', 'seo_business_street', 'seo_business_town', 'seo_business_postcode',
    'seo_business_country', 'seo_business_area_served',
)


def validate_url(value, *, path=False, fragment=False, origin=False):
    if not value:
        return
    message = _("Use an absolute HTTPS URL without credentials or a root-relative asset path where allowed.")
    if value != value.strip() or any(char.isspace() for char in value) or '\\' in value:
        raise ValidationError(message)
    parsed = urlsplit(value)
    if path and value.startswith('/') and not value.startswith('//'):
        if parsed.netloc or parsed.scheme or parsed.fragment or any(part in {'.', '..'} for part in parsed.path.split('/')) or '%' in value:
            raise ValidationError(message)
        return
    try:
        URLValidator(schemes=['https'])(value)
        parsed.port
        if parsed.username is not None or parsed.password is not None or (parsed.fragment and not fragment):
            raise ValueError()
        if origin and (parsed.path not in {'', '/'} or parsed.query or parsed.fragment):
            raise ValueError()
    except (ValidationError, ValueError):
        raise ValidationError(message) from None


def validate_discovery(site):
    errors = {}
    for field in ('seo_public_origin', 'seo_home_canonical_en', 'seo_home_canonical_fr',
                  'seo_og_url_en', 'seo_og_url_fr', 'seo_social_image', 'seo_twitter_image',
                  'seo_business_id', 'seo_business_url', 'seo_business_image', 'seo_favicon', 'seo_apple_icon'):
        try:
            validate_url(getattr(site, field), path=field in {'seo_favicon', 'seo_apple_icon'},
                         fragment=field == 'seo_business_id', origin=field == 'seo_public_origin')
        except (ValidationError, ValueError) as exc:
            errors[field] = exc.messages if isinstance(exc, ValidationError) else _("Invalid URL.")
    for field, pattern in (
        ('seo_theme_color', r'#[0-9a-fA-F]{6}'),
        ('seo_google_verification', r'[A-Za-z0-9_.-]{1,200}'),
        ('seo_bing_verification', r'[A-Za-z0-9_.-]{1,200}'),
        ('seo_locale_en', r'[a-z]{2}_[A-Z]{2}'),
        ('seo_locale_fr', r'[a-z]{2}_[A-Z]{2}'),
        ('seo_business_country', r'[A-Z]{2}'),
    ):
        value = getattr(site, field)
        if value and not re.fullmatch(pattern, value):
            errors[field] = _("Enter a value in the format shown in the example.")
    if site.seo_social_image and (not site.seo_image_width or not site.seo_image_height):
        errors['seo_image_width'] = _("Provide the image width and height in pixels.")
    if site.seo_business_enabled:
        for field in ('seo_business_name', 'seo_business_street', 'seo_business_town', 'seo_business_postcode', 'seo_business_country'):
            if not getattr(site, field).strip():
                errors[field] = _("Enter your actual business details before enabling structured data.")
    if errors:
        raise ValidationError(errors)
