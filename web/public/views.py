import logging
import re
import uuid
import secrets
from xml.etree import ElementTree
from pathlib import Path
from urllib.parse import urlsplit

from django.conf import settings
from django.core import signing
from django.db import DatabaseError
from django.db.models import Q
from django.http import FileResponse, Http404, HttpResponse, HttpResponseNotAllowed, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone, translation
from django.utils.cache import patch_vary_headers
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_GET, require_safe, require_http_methods
from django.views.decorators.debug import sensitive_post_parameters
from django.middleware.csrf import get_token
from django.utils.crypto import salted_hmac, constant_time_compare

from domain.content.models import PublicPolicy, SitePolicy, PublicItem, PublicMedia, PublicReview, PublicSiteContent, PublicTheme, PublicThemeImage, SiteContent, SiteTheme
from domain.content.theme import theme_css
from domain.content.validators import validate_instagram_url
from django.core.exceptions import ValidationError

from .copy import COPY, localised
from .metadata import READY_PAGES, absolute_url, page_metadata, canonical_url, site_origin
from web.locales import enabled_locales, preferred_locale

logger = logging.getLogger(__name__)
CURSOR_SALT = "public-feed-v1"


def health(request):
    return HttpResponse("ok", content_type="text/plain")


def _context(locale: str, page: str, site=None, *, cursor="", available=True):
    site = site or SiteContent()
    enabled = [code for code, flag in (("en", site.english_enabled), ("fr", site.french_enabled)) if flag]
    return {
        "site": site, "locale": locale, "copy": COPY[locale], "page": page,
        "seo": page_metadata(site, locale, page, cursor=cursor, available=available),
        "journal": localised(site, "journal", locale, site.default_locale) or COPY[locale]["journal"],
        "feed_heading": localised(site, "feed_heading", locale, site.default_locale) or COPY[locale]["feed_title"],
        "intro": localised(site, "intro", locale, site.default_locale),
        "footer": localised(site, "footer", locale, site.default_locale),
        "empty": localised(site, "empty", locale, site.default_locale),
        "locale_links": [(code, reverse(page, kwargs={"locale": code})) for code in enabled],
    }


def _error(request, locale, page, *, status, message, reference=""):
    context = _context(locale, page, available=False)
    context.update(message=message, reference=reference)
    context["seo"]["title"] = message
    response = render(request, "public/error.html", context, status=status)
    response["Content-Language"] = locale
    return response


@require_safe
def landing(request):
    try:
        site = PublicSiteContent.objects.first() or SiteContent()
        locale = preferred_locale(request, site)
        response = HttpResponseRedirect(reverse("feed", kwargs={"locale": locale}))
        patch_vary_headers(response, ["Accept-Language", "Cookie"])
        return response
    except DatabaseError:
        return _database_error(request, "en", "feed")


def _database_error(request, locale, page):
    reference = uuid.uuid4().hex[:12]
    # Do not log raw exception/provider/request data; it may contain secrets.
    logger.error("public_database_unavailable reference=%s", reference)
    return _error(request, locale, page, status=503, message=COPY[locale]["unavailable"], reference=reference)


@sensitive_post_parameters("email", "mobile", "message")
@require_http_methods(["GET", "HEAD", "POST"])
def public_page(request, locale="en", page="feed"):
    if locale not in COPY:
        raise Http404
    if request.method == "POST" and page != "contact":
        return HttpResponseNotAllowed(["GET", "HEAD"])
    try:
        site = PublicSiteContent.objects.first() or SiteContent()
        if not {"en": site.english_enabled, "fr": site.french_enabled}[locale]:
            raise Http404
        if page == "reviews" and not site.reviews_enabled:
            raise Http404
        context = _context(locale, page, site, available=page in READY_PAGES)
        context["theme_preview_token"] = getattr(request, "theme_preview_token", "")
        context["owner_preview"] = getattr(request, "is_owner_preview", False)
        if context["theme_preview_token"]:
            from urllib.parse import urlencode
            context["preview_query"] = "?" + urlencode({"theme_token":context["theme_preview_token"]})
            context["locale_links"] = [(code, url + context["preview_query"]) for code,url in context["locale_links"]]
        status = 200
        if page == "feed":
            query = PublicItem.objects.order_by("-effective_date", "-source_published_at", "-id")
            cursor = request.GET.get("cursor")
            if cursor:
                try:
                    if len(cursor) > 1024:
                        raise ValueError
                    values = signing.loads(cursor, salt=CURSOR_SALT, max_age=86400 * 30)
                    date, source_date, item_id = parse_datetime(values[0]), parse_datetime(values[1]), uuid.UUID(values[2])
                    if not date or not source_date or timezone.is_naive(date) or timezone.is_naive(source_date):
                        raise ValueError
                except (signing.BadSignature, ValueError, TypeError, IndexError, KeyError):
                    return _error(request, locale, page, status=400, message=COPY[locale]["invalid_cursor"])
                context["seo"] = page_metadata(site, locale, page, cursor=cursor)
                query = query.filter(
                    Q(effective_date__lt=date) |
                    Q(effective_date=date, source_published_at__lt=source_date) |
                    Q(effective_date=date, source_published_at=source_date, id__lt=item_id)
                )
            records = list(query[:site.page_size + 1])
            items = records[:site.page_size]
            assets = list(PublicMedia.objects.filter(item_id__in=[item.id for item in items]).order_by("sequence"))
            media_by_item = {}
            for asset in assets:
                media_by_item.setdefault(asset.item_id, []).append(asset)
            cards = []
            for item in items:
                try:
                    validate_instagram_url(item.canonical_url)
                except ValidationError:
                    continue
                item_assets = media_by_item.get(item.id, [])
                asset = item_assets[0] if item_assets else None
                cards.append({"item": item, "asset": asset, "alt": localised(asset, "alt", locale, site.default_locale) if asset else "",
                              "images": [{"asset": image, "alt": localised(image, "alt", locale, site.default_locale)} for image in item_assets]})
            context.update(cards=cards, paged=bool(cursor))
            if cards and cards[0]["asset"] and site_origin(site) and not context["seo"].get("image"):
                first = cards[0]
                context["seo"].update(image=absolute_url(reverse("media", args=[first["asset"].pk]), site), image_alt=first["alt"], image_width=first["asset"].width, image_height=first["asset"].height)
            if len(records) > site.page_size:
                last = items[-1]
                context["next_cursor"] = signing.dumps([last.effective_date.isoformat(), last.source_published_at.isoformat(), str(last.id)], salt=CURSOR_SALT)
        elif page == "reviews":
            # Bounded initial list; review pagination will accompany the editor.
            context["reviews"] = [
                {"record": review, "text": localised(review, "text", locale, site.default_locale)}
                for review in PublicReview.objects.order_by("-priority", "-published_at", "-id")[:48]
            ]
        elif page == "contact":
            context.update(contact_intro=localised(site, "contact_intro", locale, site.default_locale),
                contact_hours=localised(site, "contact_hours", locale, site.default_locale),
                contact_phone_link=re.sub(r"[^+0-9]", "", site.contact_phone))
            from .forms import EnquiryForm
            from domain.content.contact_mail import read_mail_settings, mail_ready, deliver_contact, DeliveryUnavailable, ContactLimited
            get_token(request)
            browser_key = salted_hmac("contact-browser-v1", request.META["CSRF_COOKIE"], algorithm="sha256").hexdigest()
            token = signing.dumps({"id":str(uuid.uuid4()), "browser":browser_key}, salt="contact-submit-v1")
            form = EnquiryForm(request.POST if request.method == "POST" else None, initial={"submission_token":token})
            context.update(enquiry_form=form, enquiry_sent=request.GET.get("sent") == "1",
                owner_preview=getattr(request, "is_owner_preview", False))
            try:
                context["mail_available"] = mail_ready(read_mail_settings(), site.contact_email)
            except (OSError, ValueError):
                context["mail_available"] = False
            if request.method == "POST":
                if form.is_valid():
                    try:
                        submission = signing.loads(form.cleaned_data["submission_token"], salt="contact-submit-v1", max_age=3600)
                        delivery_id = uuid.UUID(submission["id"])
                        if not constant_time_compare(submission["browser"], browser_key):
                            raise ValueError
                    except (signing.BadSignature, ValueError, TypeError, KeyError):
                        form.add_error(None, COPY[locale]["contact_expired"])
                        status = 400
                    else:
                        try:
                            if not form.cleaned_data["website"]:
                                deliver_contact(recipient=site.contact_email, email=form.cleaned_data["email"],
                                    mobile=form.cleaned_data["mobile"], message=form.cleaned_data["message"],
                                    address=request.META.get("REMOTE_ADDR", "unknown"), delivery_id=delivery_id)
                            return HttpResponseRedirect(reverse("contact", kwargs={"locale":locale}) + "?sent=1")
                        except ContactLimited:
                            form.add_error(None, COPY[locale]["contact_limited"])
                            status = 429
                        except DeliveryUnavailable:
                            form.add_error(None, COPY[locale]["contact_failed"])
                            status = 503
                else:
                    status = 400

        seo = context['seo']
        seo['twitter_image'] = seo.get('twitter_image') or seo.get('image')
        seo['twitter_card'] = (seo['twitter_card_setting'] if seo['twitter_card_setting'] != 'auto'
                               else 'summary_large_image' if seo.get('twitter_image') else 'summary')
        seo['nonce'] = secrets.token_urlsafe(24) if seo.get('business_json') else ''
        with translation.override(locale):
            response = render(request, f"public/{page}.html", context, status=status)
        response["Content-Language"] = locale
        response['X-Robots-Tag'] = seo['robots']
        response.structured_data_nonce = seo['nonce']
        response.icon_origins = sorted({f'{urlsplit(value).scheme}://{urlsplit(value).netloc}'
                                       for value in (seo['favicon'], seo['apple_icon']) if value.startswith('https://')})
        response.set_cookie(settings.LANGUAGE_COOKIE_NAME, locale, max_age=30 * 86400, path=settings.LANGUAGE_COOKIE_PATH, secure=settings.LANGUAGE_COOKIE_SECURE, httponly=True, samesite="Lax")
        return response
    except DatabaseError:
        return _database_error(request, locale, page)


@require_GET
def media(request, asset_id):
    try:
        asset = PublicMedia.objects.filter(pk=asset_id).first()
    except DatabaseError:
        return HttpResponse(status=503)
    if not asset:
        raise Http404
    return private_png(asset.storage_key)


def private_png(storage_key):
    if not re.fullmatch(r"[0-9a-f]{32}\.png", storage_key):
        raise Http404
    path = Path(settings.PRIVATE_MEDIA_ROOT) / storage_key
    try:
        # Managed storage is trusted; reject symlinks rather than follow them.
        if path.is_symlink():
            raise Http404
        return FileResponse(path.open("rb"), content_type="image/png")
    except OSError:
        raise Http404


@require_safe
def stylesheet(request):
    try:
        theme = PublicTheme.objects.first() or SiteTheme()
        image_url = reverse("theme_image", args=[theme.background_image_id]) if theme.background_image_id else ""
        css = theme_css(theme, image_url=image_url)
        return HttpResponse(css, content_type="text/css; charset=utf-8")
    except ValidationError:
        return HttpResponse(theme_css(SiteTheme()), content_type="text/css; charset=utf-8")
    except DatabaseError:
        return HttpResponse(theme_css(SiteTheme()), content_type="text/css; charset=utf-8", status=503)


@require_GET
def theme_image(request, asset_id):
    try:
        asset = PublicThemeImage.objects.filter(pk=asset_id).first()
    except DatabaseError:
        return HttpResponse(status=503)
    if not asset:
        raise Http404
    return private_png(asset.storage_key)


def not_found(request, exception):
    locale = "fr" if request.path.startswith(settings.APP_SCRIPT_PREFIX + "/fr/") else "en"
    return _error(request, locale, "feed", status=404, message=COPY[locale]["not_found"])


def server_error(request):
    locale = "fr" if request.path.startswith(settings.APP_SCRIPT_PREFIX + "/fr/") else "en"
    return _error(request, locale, "feed", status=500, message=COPY[locale]["unavailable"])


@require_safe
def robots(request):
    public = settings.ROOT_URLCONF in {"web.public.urls", "web.public.prefixed_urls"}
    try:
        site = (PublicSiteContent.objects.first() or SiteContent()) if public else SiteContent()
        if public and not settings.LOCAL and settings.PUBLIC_INDEXING_ENABLED and site_origin(site) and site.seo_robots != 'noindex':
            text = "User-agent: *\nAllow: /\nSitemap: " + absolute_url(reverse("sitemap"), site) + "\n"
        else:
            text = "User-agent: *\nDisallow: /\n"
    except DatabaseError:
        text = "User-agent: *\nDisallow: /\n"
    return HttpResponse(text, content_type="text/plain; charset=utf-8")


@require_safe
def sitemap(request):
    try:
        site = PublicSiteContent.objects.first() or SiteContent()
        if not site_origin(site):
            return HttpResponse(status=503)
        namespace = "http://www.sitemaps.org/schemas/sitemap/0.9"
        alternate = "http://www.w3.org/1999/xhtml"
        ElementTree.register_namespace("", namespace)
        ElementTree.register_namespace("xhtml", alternate)
        root = ElementTree.Element(f"{{{namespace}}}urlset")
        codes = enabled_locales(site)
        for page in READY_PAGES:
            if page == "reviews" and not site.reviews_enabled:
                continue
            for code in codes:
                node = ElementTree.SubElement(root, f"{{{namespace}}}url")
                ElementTree.SubElement(node, f"{{{namespace}}}loc").text = canonical_url(site, code, page)
                for language in (*codes, "x-default"):
                    target = site.default_locale if language == "x-default" else language
                    ElementTree.SubElement(node, f"{{{alternate}}}link", rel="alternate", hreflang=language, href=canonical_url(site, target, page))
        response = HttpResponse(ElementTree.tostring(root, encoding="utf-8", xml_declaration=True), content_type="application/xml; charset=utf-8")
        response["X-Robots-Tag"] = "noindex, follow"
        return response
    except DatabaseError:
        logger.error("sitemap_database_unavailable")
        return HttpResponse(status=503)


@require_safe
def privacy(request):
    from domain.content.policy import policy_context
    try:
        record = PublicPolicy.objects.first() or SitePolicy()
    except DatabaseError:
        # The published artifact remains readable during a database outage.
        try:
            body = Path(settings.POLICY_EXPORT_FILE).read_bytes()
        except OSError:
            record = SitePolicy()
        else:
            response = HttpResponse(body, content_type="text/html; charset=utf-8")
            response["Content-Language"] = "en"
            response["X-Robots-Tag"] = "noindex, follow"
            return response
    with translation.override("en"):
        response = render(request, "public/privacy.html", policy_context(record))
    response["Content-Language"] = "en"
    response["X-Robots-Tag"] = "noindex, follow"
    return response
