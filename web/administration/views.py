import logging
import uuid
from functools import wraps
from urllib.parse import urlencode, urlsplit

from django.conf import settings
from django.contrib import auth
from django.contrib.auth.forms import PasswordChangeForm
from django.core.exceptions import ValidationError
from django.core import signing
from django.core.paginator import Paginator
from django.db import DatabaseError, transaction
from django.db.models import Q
from django.http import Http404, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_GET, require_http_methods, require_POST, require_safe

from domain.content.editing import EditConflict, CONTACT_FIELDS, REVIEW_FIELDS, ITEM_FIELDS, SITE_FIELDS, delete_story, edit_content, require_owner
from domain.content.models import AuditEvent, ContentRevision, LoginCounter, MediaAsset, MediaQuota, PresentationItem, SiteContent, SitePolicy, SiteTheme, ThemeImage
from domain.content.policy import POLICY_FIELDS, policy_context
from domain.content.theme import THEME_FIELDS, theme_css
from domain.content.restoration import SETTINGS_MODELS, prepare_restoration, restore_settings, settings_model
from domain.content.uploads import edit_item_image, edit_theme
from domain.content.discovery import DISCOVERY_FIELDS
from domain.content.metadata import SEO_FIELDS
from domain.content.validators import validate_instagram_url
from web.public.metadata import page_metadata

from .forms import PolicyForm, ContactForm, ReviewsForm, DeleteStoryForm, DiscoveryForm, ItemForm, ItemImageForm, OwnerAuthenticationForm, RestoreSettingsForm, SearchForm, SiteForm, ThemeForm
from .security import counter_key, reserve_login
from .locales import enabled_locales

logger = logging.getLogger(__name__)


def _unavailable(request):
    reference = uuid.uuid4().hex[:12]
    logger.error("admin_database_unavailable reference=%s", reference)
    return render(request, "administration/unavailable.html", {"reference": reference}, status=503)


def owner_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return HttpResponseRedirect(reverse("owner_login") + "?" + urlencode({"next": request.get_full_path()}))
        try:
            require_owner(request.user)
            return view(request, *args, **kwargs)
        except DatabaseError:
            return _unavailable(request)
    return wrapped


@require_http_methods(["GET", "POST"])
def login(request):
    form = OwnerAuthenticationForm(request, data=request.POST if request.method == "POST" else None)
    if request.method == "POST":
        username = request.POST.get("username", "")
        try:
            wait = reserve_login(username, request.META.get("REMOTE_ADDR", "unknown"))
            if wait:
                response = render(request, "administration/login.html", {"form": OwnerAuthenticationForm(request), "limited": True}, status=429)
                response["Retry-After"] = str(wait)
                return response
            if form.is_valid():
                user = form.get_user()
                with transaction.atomic():
                    AuditEvent.objects.create(actor=user, action="login", entity="owner", entity_id=str(user.pk))
                    LoginCounter.objects.filter(pk=counter_key("account", username)).delete()
                    prior_session_key = request.session.session_key
                    auth.login(request, user)
                    if request.session.session_key == prior_session_key:
                        request.session.cycle_key()
                    now = timezone.now().timestamp()
                    request.session["owner_login_at"] = now
                    request.session["owner_seen_at"] = now
                destination = request.POST.get("next", "")
                if not url_has_allowed_host_and_scheme(destination, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
                    destination = ""
                return HttpResponseRedirect(destination or reverse("owner_items"))
        except DatabaseError:
            request.session.clear()
            return _unavailable(request)
    return render(request, "administration/login.html", {"form": form, "next": request.GET.get("next", request.POST.get("next", ""))})


@require_POST
@owner_required
def logout(request):
    with transaction.atomic():
        AuditEvent.objects.create(actor=request.user, action="logout", entity="owner", entity_id=str(request.user.pk))
        auth.logout(request)
    return HttpResponseRedirect(reverse("owner_login"))


@require_safe
@owner_required
def items(request):
    form = SearchForm(request.GET)
    query = PresentationItem.objects.filter(deleted_at__isnull=True).order_by("-source_published_at", "-id")
    if form.is_valid():
        data = form.cleaned_data
        if data["q"]:
            query = query.filter(Q(original_caption__icontains=data["q"]) | Q(display_caption__icontains=data["q"]) | Q(source_post_id__icontains=data["q"]) | Q(canonical_url__icontains=data["q"]))
        if data["status"]:
            query = query.filter(status=data["status"])
        if data["start"]:
            query = query.filter(source_published_at__date__gte=data["start"])
        if data["end"]:
            query = query.filter(source_published_at__date__lte=data["end"])
    else:
        query = query.none()
    page = Paginator(query, 25).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    return render(request, "administration/items.html", {"form": form, "items": page, "query_params": params.urlencode()}, status=200 if form.is_valid() else 400)


def _editor(request, *, model, pk, form_class, fields, template, extra_context=None):
    query = model.objects.filter(deleted_at__isnull=True) if model is PresentationItem else model.objects.all()
    obj = get_object_or_404(query, pk=pk)
    form = form_class(request.POST if request.method == "POST" else None, instance=obj, initial={"version": obj.version})
    status, saved, preview = 200, False, False
    if request.method == "POST" and form.is_valid():
        if "preview" in request.POST:
            preview = True
        else:
            try:
                backup = None
                shared_email_changed = model is SiteContent and "contact_email" in fields and SiteContent.objects.get(pk=pk).contact_email != form.cleaned_data["contact_email"]
                with transaction.atomic():
                    obj = edit_content(actor=request.user, model=model, pk=pk, expected_version=form.cleaned_data["version"], changes={field: form.cleaned_data[field] for field in fields}, confirm_hide=form.cleaned_data.get("confirm_hide", False))
                    if shared_email_changed:
                        from web.public.policy import export_policy
                        backup = export_policy(SitePolicy.objects.select_for_update().get(pk=1))
                form = form_class(instance=obj, initial={"version": obj.version})
                saved = True
            except (OSError, DatabaseError):
                if backup is not None:
                    from web.public.policy import restore_export
                    restore_export(backup)
                return _unavailable(request)
            except EditConflict:
                form.add_error(None, _("This record changed in another tab. Your input is retained. Reload the current record before saving again."))
                status = 409
            except ValidationError as exc:
                form.add_error(None, ValidationError(exc.messages))
                status = 400
    elif request.method == "POST":
        status = 400
    safe_source_url = ""
    if model is SiteContent and saved:
        request.admin_site = obj
    if model is PresentationItem:
        try:
            validate_instagram_url(obj.canonical_url)
            safe_source_url = obj.canonical_url
        except ValidationError:
            pass
    metadata_previews = [dict(code=code, **page_metadata(form.instance, code, page)) for page in ("feed", "reviews", "contact") for code in ("en", "fr")] if model is SiteContent and preview else []
    return render(request, template, {"form": form, "record": obj, "saved": saved, "preview": preview, "safe_source_url": safe_source_url, "metadata_previews": metadata_previews, **(extra_context or {})}, status=status)


@require_http_methods(["GET", "POST"])
@owner_required
def item_edit(request, item_id):
    return _editor(request, model=PresentationItem, pk=item_id, form_class=ItemForm, fields=ITEM_FIELDS, template="administration/item_edit.html")


@require_http_methods(["GET", "POST"])
@owner_required
def site_edit(request):
    return _editor(request, model=SiteContent, pk=1, form_class=SiteForm, fields=SITE_FIELDS, template="administration/site_edit.html")


@require_http_methods(["GET", "POST"])
@owner_required
def discovery_edit(request):
    return _editor(request, model=SiteContent, pk=1, form_class=DiscoveryForm,
                   fields=('name', *SEO_FIELDS, *DISCOVERY_FIELDS),
                   template="administration/discovery.html")


@require_safe
@owner_required
def audit(request):
    events = AuditEvent.objects.select_related("actor", "revision").order_by("-created_at", "-id")
    entity = request.GET.get("entity")
    if entity in SETTINGS_MODELS:
        events = events.filter(entity=entity)
    events = events[:100]
    return render(request, "administration/audit.html", {"events": events})


@require_safe
@owner_required
def revision(request, revision_id):
    record = get_object_or_404(ContentRevision, pk=revision_id)
    can_restore = record.entity in SETTINGS_MODELS and record.entity_id == "1"
    return render(request, "administration/revision.html", {"revision": record, "can_restore": can_restore})


@require_http_methods(["GET", "POST"])
@owner_required
def settings_restore(request, revision_id):
    source = get_object_or_404(ContentRevision, pk=revision_id)
    if source.entity not in SETTINGS_MODELS or source.entity_id != "1":
        raise Http404
    model = settings_model(source)[0]
    current = get_object_or_404(model, pk=1)
    form = RestoreSettingsForm(request.POST if request.method == "POST" else None, initial={"version": current.version})
    status, error, target, changes = 200, "", None, {}
    if request.method == "POST" and form.is_valid():
        backup = None
        try:
            with transaction.atomic():
                restored = restore_settings(actor=request.user, revision_id=source.pk, expected_version=form.cleaned_data["version"], confirmed=form.cleaned_data["confirm"])
                if model is SitePolicy or (model is SiteContent and current.contact_email != restored.contact_email):
                    from web.public.policy import export_policy
                    published_policy = restored if model is SitePolicy else SitePolicy.objects.select_for_update().get(pk=1)
                    backup = export_policy(published_policy)
            destination = "owner_site" if model is SiteContent else "owner_policy" if model is SitePolicy else "owner_theme"
            return HttpResponseRedirect(reverse(destination) + "?restored=1")
        except (OSError, DatabaseError):
            if backup is not None:
                from web.public.policy import restore_export
                restore_export(backup)
            return _unavailable(request)
        except EditConflict:
            form.add_error(None, _("These settings changed after you opened this page. Reload the comparison and confirm again."))
            status = 409
        except ValidationError as exc:
            form.add_error(None, ValidationError(exc.messages))
            status = 400
    elif request.method == "POST":
        status = 400
    try:
        target, changes = prepare_restoration(current, source)
    except ValidationError as exc:
        error = "; ".join(exc.messages)
        status = 400 if status == 200 else status
    labels = {**SiteForm.base_fields, **DiscoveryForm.base_fields, **ContactForm.base_fields, **ReviewsForm.base_fields} if model is SiteContent else PolicyForm.base_fields if model is SitePolicy else ThemeForm.base_fields
    rows = []
    for field, value in changes.items():
        before = getattr(current, field)
        if field == "background_image_id":
            label = _("Background image")
            before = _("Saved image") if before else _("No image")
            value = _("Saved image") if value else _("No image")
        else:
            label = labels[field].label
            if isinstance(value, bool):
                before = _("Enabled") if before else _("Disabled")
                value = _("Enabled") if value else _("Disabled")
        rows.append({"label": label, "before": before, "after": value, "background": field == "background_image_id"})
    return render(request, "administration/settings_restore.html", {"revision": source, "current": current, "target": target, "rows": rows, "form": form, "error": error}, status=status)


@require_http_methods(["GET", "POST"])
@owner_required
def item_image(request, item_id):
    item = get_object_or_404(PresentationItem, pk=item_id, deleted_at__isnull=True)
    asset = MediaAsset.objects.filter(item=item, active=True).order_by("sequence", "id").first()
    initial = {"version": item.version, "alt_en": asset.alt_en if asset else "", "alt_fr": asset.alt_fr if asset else ""}
    form = ItemImageForm(request.POST if request.method == "POST" else None, request.FILES or None, initial=initial)
    status, saved = 200, False
    if request.method == "POST" and form.is_valid():
        try:
            item = edit_item_image(actor=request.user, item_id=item.pk, expected_version=form.cleaned_data["version"], alt_en=form.cleaned_data["alt_en"], alt_fr=form.cleaned_data["alt_fr"], image=form.cleaned_data.get("image"))
            asset = MediaAsset.objects.filter(item=item, active=True).order_by("sequence", "id").first()
            form = ItemImageForm(initial={"version": item.version, "alt_en": asset.alt_en, "alt_fr": asset.alt_fr})
            saved = True
        except EditConflict:
            form.add_error(None, _("This story changed. Reload the current version, keep your descriptions, and reselect the image before saving."))
            status = 409
        except ValidationError as exc:
            form.add_error(None, ValidationError(exc.messages))
            status = 400
        except OSError:
            return _unavailable(request)
    elif request.method == "POST":
        status = 400
    quota = MediaQuota.objects.get(pk=1)
    return render(request, "administration/item_image.html", {"form": form, "record": item, "asset": asset, "saved": saved, "quota": quota, "budget_warning": quota.bytes_used * 5 >= settings.MEDIA_STORAGE_LIMIT_BYTES * 4}, status=status)


@require_GET
@owner_required
def private_image(request, asset_id, kind):
    from web.public.views import private_png
    model = MediaAsset if kind == "item" else ThemeImage
    asset = get_object_or_404(model, pk=asset_id, validated=True)
    return private_png(asset.storage_key)


@require_http_methods(["GET", "POST"])
@owner_required
def theme_edit(request):
    theme = get_object_or_404(SiteTheme, pk=1)
    form = ThemeForm(request.POST if request.method == "POST" else None, request.FILES or None, instance=theme, initial={"version": theme.version})
    status, saved, token = 200, False, ""
    if request.method == "POST" and form.is_valid():
        if "preview" in request.POST:
            token = signing.dumps({field: form.cleaned_data[field] for field in THEME_FIELDS}, salt="theme-preview-v1")
            site = SiteContent.objects.first() or SiteContent()
            return HttpResponseRedirect(reverse("feed", kwargs={"locale": site.default_locale}) + "?" + urlencode({"theme_token": token}))
        else:
            try:
                theme = edit_theme(actor=request.user, expected_version=form.cleaned_data["version"], changes={field: form.cleaned_data[field] for field in THEME_FIELDS}, image=form.cleaned_data.get("image"), clear_background=form.cleaned_data["clear_background"])
                form = ThemeForm(instance=theme, initial={"version": theme.version})
                saved = True
            except EditConflict:
                form.add_error(None, _("The theme changed in another tab. Reload the current version before saving; reselect any upload."))
                status = 409
            except ValidationError as exc:
                form.add_error(None, ValidationError(exc.messages))
                status = 400
            except OSError:
                return _unavailable(request)
    elif request.method == "POST":
        status = 400
    quota = MediaQuota.objects.get(pk=1)
    return render(request, "administration/theme.html", {"form": form, "record": theme, "saved": saved, "preview_token": token, "budget_warning": quota.bytes_used * 5 >= settings.MEDIA_STORAGE_LIMIT_BYTES * 4}, status=status)


@require_safe
@owner_required
def theme_preview(request):
    token = request.GET.get("token", "")
    try:
        if len(token) > 2048:
            raise ValueError
        values = signing.loads(token, salt="theme-preview-v1", max_age=600)
        if not isinstance(values, dict) or set(values) != set(THEME_FIELDS):
            raise ValueError
        candidate = SiteTheme(**values)
        candidate.clean()
        image_url = ""
        if request.GET.get("full") == "1":
            theme = SiteTheme.objects.get(pk=1)
            if theme.background_image_id:
                image_url = reverse("owner_theme_image", args=[theme.background_image_id])
        css = theme_css(candidate, preview=request.GET.get("full") != "1", image_url=image_url)
    except (signing.BadSignature, ValidationError, ValueError, TypeError):
        raise Http404
    return HttpResponse(css, content_type="text/css; charset=utf-8")


@require_POST
def set_language(request):
    try:
        site = SiteContent.objects.first() or SiteContent()
    except DatabaseError:
        return _unavailable(request)
    locale = request.POST.get("language")
    if locale not in enabled_locales(site):
        return HttpResponse(_("Choose an enabled language."), status=400)
    destination = request.POST.get("next", "")
    valid = url_has_allowed_host_and_scheme(destination, allowed_hosts={request.get_host()}, require_https=request.is_secure())
    if not valid or not urlsplit(destination).path.startswith(f"/{settings.ADMIN_SLUG}/"):
        destination = reverse("owner_items") if request.user.is_authenticated else reverse("owner_login")
    response = HttpResponseRedirect(destination)
    response.set_cookie(settings.LANGUAGE_COOKIE_NAME, locale, max_age=30 * 86400, path=settings.LANGUAGE_COOKIE_PATH, secure=settings.LANGUAGE_COOKIE_SECURE, httponly=True, samesite="Lax")
    response["Content-Language"] = locale
    return response


@sensitive_post_parameters('password', 'verification_code')
@require_http_methods(["GET", "POST"])
@owner_required
def instagram_setup(request):
    from .forms import InstagramAccountForm, InstagramConnectForm, InstagramRecentForm
    from .instagram_client import InstagramAgent, InstagramUnavailable
    from domain.content.instagram_import import load_recent
    account_form = InstagramAccountForm()
    connect_form = InstagramConnectForm()
    recent_form = InstagramRecentForm()
    status, error, notice, summary = {}, '', '', None
    agent = None
    try:
        agent = InstagramAgent()
        status = agent.call('status')
        account_form = InstagramAccountForm(initial={'username': status.get('username', '')})
        if request.method == 'POST':
            action = request.POST.get('action')
            if action == 'account':
                account_form = InstagramAccountForm(request.POST)
                if account_form.is_valid():
                    agent.call('account', account_form.cleaned_data)
                    notice = _("Account details saved securely. Connect to verify access.")
                    account_form = InstagramAccountForm(initial={'username': account_form.cleaned_data['username']})
            elif action == 'connect':
                connect_form = InstagramConnectForm(request.POST)
                if connect_form.is_valid():
                    agent.call('connect', connect_form.cleaned_data)
                    notice = _("Instagram account verified. You can now load recent posts.")
                    connect_form = InstagramConnectForm()
            elif action == 'recent':
                recent_form = InstagramRecentForm(request.POST)
                if recent_form.is_valid():
                    summary = load_recent(actor=request.user, agent=agent, limit=recent_form.cleaned_data['limit'])
                    notice = _("Import finished. Valid new stories are now visible on the public website.")
            else:
                return HttpResponse(_("Choose a supported Instagram action."), status=400)
            status = agent.call('status')
    except InstagramUnavailable as exc:
        error = str(exc)
    except ValidationError as exc:
        error = ' '.join(exc.messages)
    # Never retain a submitted password/code in rendered form values or sessions.
    if request.method == 'POST' and request.POST.get('action') == 'connect':
        connect_form = InstagramConnectForm()
    return render(request, "administration/instagram.html", {
        'connection': status, 'account_form': account_form, 'connect_form': connect_form,
        'recent_form': recent_form, 'error': error, 'notice': notice, 'summary': summary,
    }, status=400 if error and request.method == 'POST' else 200)


@require_http_methods(["GET", "POST"])
@owner_required
def contact_edit(request):
    from .forms import ContactMailForm
    from domain.content.contact_mail import read_mail_settings
    try:
        config = read_mail_settings()
    except (OSError, ValueError):
        return _unavailable(request)
    return _editor(request, model=SiteContent, pk=1, form_class=ContactForm,
        fields=CONTACT_FIELDS, template="administration/contact.html",
        extra_context={"mail_form": ContactMailForm(initial={key:value for key,value in config.items() if key != 'password'}),
            "mail_password_saved": bool(config['password'])})


@require_http_methods(["GET", "POST"])
@owner_required
def reviews_edit(request):
    return _editor(request, model=SiteContent, pk=1, form_class=ReviewsForm,
        fields=REVIEW_FIELDS, template="administration/reviews.html")


@sensitive_post_parameters("old_password", "new_password1", "new_password2")
@require_http_methods(["GET", "POST"])
@owner_required
def password_change(request):
    form = PasswordChangeForm(request.user, request.POST if request.method == "POST" else None)
    status = 200
    if request.method == "POST":
        wait = reserve_login(request.user.username, request.META.get("REMOTE_ADDR", "unknown"))
        if wait:
            response = render(request, "administration/password.html", {"form": PasswordChangeForm(request.user), "limited": True}, status=429)
            response["Retry-After"] = str(wait)
            return response
        if form.is_valid():
            with transaction.atomic():
                AuditEvent.objects.create(actor=request.user, action="change_password", entity="owner", entity_id=str(request.user.pk))
                user = form.save(commit=False)
                user.save(update_fields=["password"])
                LoginCounter.objects.filter(pk=counter_key("account", user.username)).delete()
            auth.update_session_auth_hash(request, user)
            return HttpResponseRedirect(reverse("owner_password") + "?saved=1")
        status = 400
    return render(request, "administration/password.html", {"form": form}, status=status)


@require_http_methods(["GET", "POST"])
@owner_required
def item_delete(request, item_id):
    item = get_object_or_404(PresentationItem, pk=item_id, deleted_at__isnull=True)
    form = DeleteStoryForm(request.POST if request.method == "POST" else None, initial={"version": item.version})
    status = 200
    if request.method == "POST":
        if form.is_valid():
            try:
                delete_story(actor=request.user, pk=item.pk, expected_version=form.cleaned_data["version"])
                return HttpResponseRedirect(reverse("owner_items") + "?deleted=1")
            except EditConflict:
                form.add_error(None, _("This story changed in another tab. Reload and review it before deleting."))
                status = 409
        else:
            status = 400
    return render(request, "administration/item_delete.html", {"form": form, "record": item}, status=status)


@sensitive_post_parameters("password")
@require_POST
@owner_required
def contact_mail_edit(request):
    from .forms import ContactMailForm
    from domain.content.contact_mail import save_mail_settings
    form = ContactMailForm(request.POST)
    status = 400
    if form.is_valid():
        try:
            save_mail_settings(actor=request.user, values=form.cleaned_data)
            return HttpResponseRedirect(reverse("owner_contact") + "?mail_saved=1#email-delivery")
        except EditConflict:
            form.add_error(None, _("Email settings changed in another tab. Reload before saving again."))
            status = 409
        except (OSError, ValueError):
            return _unavailable(request)
    record = SiteContent.objects.get(pk=1)
    return render(request, "administration/contact.html", {"record":record,
        "form":ContactForm(instance=record, initial={"version":record.version}), "mail_form":form}, status=status)


@require_http_methods(["GET", "POST"])
@owner_required
def policy_edit(request):
    from web.public.policy import export_policy, restore_export
    record = get_object_or_404(SitePolicy, pk=1)
    form = PolicyForm(request.POST if request.method == "POST" else None, instance=record,
        initial={"version":record.version})
    status, saved, preview = 200, False, False
    if request.method == "POST":
        if form.is_valid():
            if "preview" in request.POST:
                preview = True
            else:
                backup = None
                try:
                    with transaction.atomic():
                        record = edit_content(actor=request.user, model=SitePolicy, pk=1,
                            expected_version=form.cleaned_data["version"],
                            changes={name:form.cleaned_data[name] for name in POLICY_FIELDS})
                        backup = export_policy(record)
                    form = PolicyForm(instance=record, initial={"version":record.version})
                    saved = True
                except EditConflict:
                    form.add_error(None, _("This record changed in another tab. Your input is retained. Reload the current record before saving again."))
                    status = 409
                except ValidationError as exc:
                    form.add_error(None, ValidationError(exc.messages))
                    status = 400
                except (OSError, DatabaseError):
                    if backup is not None:
                        restore_export(backup)
                    return _unavailable(request)
        else:
            status = 400
    site = SiteContent.objects.first()
    from domain.content.policy import DEFAULT_POLICY_EMAIL
    context = policy_context(form.instance, contact_email=site.contact_email if site is not None else DEFAULT_POLICY_EMAIL)
    context.update(form=form, record=record, saved=saved, preview=preview)
    return render(request, "administration/policy.html", context, status=status)
