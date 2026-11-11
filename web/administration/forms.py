from django.utils.translation import gettext_lazy as _
from django import forms
from django.contrib.auth.forms import AuthenticationForm

from domain.content.editing import ITEM_FIELDS, SITE_FIELDS
from domain.content.metadata import SEO_FIELDS
from domain.content.models import PresentationItem, SiteContent, SiteOwner, SiteTheme, Status
from domain.content.theme import THEME_FIELDS


class OwnerAuthenticationForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = _("Username")
        self.fields["password"].label = _("Password")

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_staff or not SiteOwner.objects.filter(pk=1, user=user).exists():
            raise self.get_invalid_login_error()


class ItemForm(forms.ModelForm):
    version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    confirm_hide = forms.BooleanField(required=False, label=_("I confirm removing this published story from the public feed"))

    class Meta:
        model = PresentationItem
        fields = ITEM_FIELDS
        labels = {"display_caption": _("Display caption"), "display_date": _("Display date"), "priority": _("Priority"), "status": _("Status"), "publish_at": _("Publish at")}
        widgets = {"display_caption": forms.Textarea(attrs={"rows": 9}), "display_date": forms.DateTimeInput(), "publish_at": forms.DateTimeInput()}
        help_texts = {"display_caption": _("Leave blank to use the original caption. Keep its original language."), "display_date": _("Local site time (Europe/London). Format: YYYY-MM-DD HH:MM:SS."), "publish_at": _("Publication time in Europe/London. Required for Published status.")}


class SiteForm(forms.ModelForm):
    version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)

    class Meta:
        model = SiteContent
        fields = SITE_FIELDS
        labels = {
            "journal_en": _("Journal label (English)"), "journal_fr": _("Journal label (French)"),
            "feed_heading_en": _("Main feed heading (English)"), "feed_heading_fr": _("Main feed heading (French)"),
            "name": _("Site name"), "intro_en": _("Introduction (English)"), "intro_fr": _("Introduction (French)"),
            "footer_en": _("Footer (English)"), "footer_fr": _("Footer (French)"),
            "empty_en": _("Empty feed message (English)"), "empty_fr": _("Empty feed message (French)"),
            "seo_feed_title_en": _("Feed title (English)"),
            "seo_feed_title_fr": _("Feed title (French)"),
            "seo_feed_description_en": _("Feed description (English)"),
            "seo_feed_description_fr": _("Feed description (French)"),
            "seo_reviews_title_en": _("Reviews title (English)"),
            "seo_reviews_title_fr": _("Reviews title (French)"),
            "seo_reviews_description_en": _("Reviews description (English)"),
            "seo_reviews_description_fr": _("Reviews description (French)"),
            "seo_contact_title_en": _("Contact title (English)"),
            "seo_contact_title_fr": _("Contact title (French)"),
            "seo_contact_description_en": _("Contact description (English)"),
            "seo_contact_description_fr": _("Contact description (French)"),
            "default_locale": _("Default language"), "english_enabled": _("Enable English"),
            "french_enabled": _("Enable French"), "page_size": _("Stories per page"),
        }
        help_texts = {field: _("Leave blank to use the locale fallback and page defaults. Plain text only.") for field in SEO_FIELDS}
        widgets = {field: forms.Textarea(attrs={"rows": 3}) for field in SITE_FIELDS if field.startswith(("intro_", "footer_", "empty_"))}


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from web.public.copy import COPY
        for code in ("en", "fr"):
            for stem, key in (("journal", "journal"), ("feed_heading", "feed_title")):
                field = self.fields[f"{stem}_{code}"]
                field.widget.attrs["placeholder"] = COPY[code][key]
                field.help_text = _("Leave blank to use the language fallback or the default text. Plain text only.")

    @property
    def groups(self):
        feed_fields = ("journal_en", "journal_fr", "feed_heading_en", "feed_heading_fr", "intro_en", "intro_fr")
        return [(_("Main feed introduction"), [self[name] for name in feed_fields]),
            (_("Site settings"), [self[name] for name in SITE_FIELDS if name not in feed_fields])]


class SearchForm(forms.Form):
    q = forms.CharField(max_length=200, required=False, label=_("Search caption, source ID or URL"))
    status = forms.ChoiceField(choices=[("", _("All statuses")), *Status.choices], required=False, label=_("Status"))
    start = forms.DateField(required=False, label=_("From date"), widget=forms.DateInput(attrs={"type": "date"}))
    end = forms.DateField(required=False, label=_("To date"), widget=forms.DateInput(attrs={"type": "date"}))

    def clean(self):
        data = super().clean()
        if data.get("start") and data.get("end") and data["start"] > data["end"]:
            raise forms.ValidationError(_("The start date must precede the end date."))
        return data


class ItemImageForm(forms.Form):
    version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    image = forms.FileField(required=False, label=_("New image"), help_text=_("Single PNG, JPEG or WebP, up to 10 MiB and 20 million pixels. Leave blank to edit descriptions only."))
    alt_en = forms.CharField(max_length=500, label=_("Image description (English)"))
    alt_fr = forms.CharField(max_length=500, required=False, label=_("Image description (French)"))


class ThemeForm(forms.ModelForm):
    version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    image = forms.FileField(required=False, label=_("New decorative background image"), help_text=_("PNG, JPEG or WebP, up to 10 MiB. Uploads are applied on Save; previews show colours and fonts."))
    clear_background = forms.BooleanField(required=False, label=_("Remove the current background image"))

    class Meta:
        model = SiteTheme
        fields = THEME_FIELDS
        labels = {"background_color": _("Page colour"), "text_color": _("Text colour"), "muted_color": _("Secondary text colour"), "accent_color": _("Accent colour"), "font": _("Font")}

    def clean(self):
        data = super().clean()
        if data.get("image") and data.get("clear_background"):
            raise forms.ValidationError(_("Choose an upload or remove the background, not both."))
        return data


class RestoreSettingsForm(forms.Form):
    version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    confirm = forms.BooleanField(label=_("I confirm replacing the current settings with this saved version."))


class InstagramAccountForm(forms.Form):
    username = forms.RegexField(regex=r'^[A-Za-z0-9._]{1,30}$', max_length=30, label=_("Instagram username"))
    password = forms.CharField(required=False, max_length=1024, strip=False,
        label=_("Instagram password"), widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
        help_text=_("Leave blank to keep the saved password for this username."))


class InstagramConnectForm(forms.Form):
    verification_code = forms.RegexField(regex=r'^[0-9]{6,8}$', max_length=8, required=False,
        label=_("Two-factor or backup code (when requested)"),
        widget=forms.TextInput(attrs={'autocomplete': 'one-time-code', 'inputmode': 'numeric'}))


class InstagramRecentForm(forms.Form):
    limit = forms.IntegerField(min_value=1, max_value=12, initial=6, label=_("Recent posts to load"))


from django.utils.text import format_lazy
from domain.content.discovery import DISCOVERY_FIELDS


class DiscoveryForm(forms.ModelForm):
    version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)

    class Meta:
        model = SiteContent
        fields = ('name', *SEO_FIELDS, *DISCOVERY_FIELDS)
        labels = {
            **SiteForm.Meta.labels,
            'seo_public_origin': _("Public website origin"),
            'seo_home_canonical_en': _("Homepage canonical URL (EN)"),
            'seo_home_canonical_fr': _("Homepage canonical URL (FR)"),
            'seo_robots': _("Search engine indexing"),
            'seo_max_image_preview': _("Maximum image preview"),
            'seo_social_site_name': _("Social site name"),
            'seo_og_type': _("Open Graph type"),
            'seo_social_image': _("Default social image URL"),
            'seo_image_width': _("Social image width (pixels)"),
            'seo_image_height': _("Social image height (pixels)"),
            'seo_locale_en': _("Open Graph locale (EN)"),
            'seo_locale_fr': _("Open Graph locale (FR)"),
            'seo_twitter_card': _("X / Twitter card"),
            'seo_twitter_image': _("X / Twitter image URL"),
            'seo_favicon': _("Favicon URL or path"),
            'seo_apple_icon': _("Apple touch icon URL or path"),
            'seo_theme_color': _("Browser theme colour"),
            'seo_google_verification': _("Google verification token"),
            'seo_bing_verification': _("Bing verification token"),
            'seo_business_enabled': _("Publish business structured data"),
            'seo_business_type': _("Business schema type"),
            'seo_business_id': _("Business identifier URL (@id)"),
            'seo_business_name': _("Business name"),
            'seo_business_url': _("Business website URL"),
            'seo_business_image': _("Business image URL"),
            'seo_business_price_range': _("Price range"),
            'seo_business_street': _("Street address"),
            'seo_business_town': _("Town or city"),
            'seo_business_postcode': _("Postcode"),
            'seo_business_country': _("Country code"),
            'seo_business_area_served': _("Country served"),
        }
        help_texts = {
            'seo_public_origin': _("Your HTTPS domain, for example https://yourbrand.com. Blank uses the current website address."),
            'seo_home_canonical_en': _("Optional exact homepage URL. Other pages keep their own canonical URLs."),
            'seo_home_canonical_fr': _("Optional exact French homepage URL."),
            'seo_robots': _("Private previews stay hidden from search engines. Indexing also requires the public deployment to allow it."),
            'seo_social_image': _("An existing HTTPS image URL. Enter its actual dimensions and a description below."),
            'seo_twitter_image': _("Blank uses the default social image or the first published image."),
            'seo_favicon': _("An existing asset, for example /favicon.ico or an HTTPS URL. This field does not upload a file."),
            'seo_apple_icon': _("An existing asset, for example /apple-touch-icon.png or an HTTPS URL."),
            'seo_theme_color': _("Six-digit hex colour, for example #ffffff."),
            'seo_google_verification': _("Paste only the verification token, not a meta tag. It will be public."),
            'seo_bing_verification': _("Paste only the verification token, not a meta tag. It will be public."),
            'seo_business_enabled': _("Enable only after entering your real business name and address. These details will be public."),
            'seo_business_id': _("Blank uses your business URL followed by #business."),
            'seo_business_url': _("Blank uses your public website origin."),
            'seo_business_image': _("Blank uses the default social image."),
            'seo_business_price_range': _("For example ££. Leave blank if not applicable."),
            'seo_business_country': _("Two-letter country code, for example GB."),
            'seo_business_area_served': _("Country name, for example United Kingdom."),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for stem, label in (
            ('og_title', _("Open Graph title")), ('og_description', _("Open Graph description")),
            ('og_url', _("Homepage Open Graph URL")), ('image_alt', _("Social image description")),
            ('twitter_title', _("X / Twitter title")), ('twitter_description', _("X / Twitter description")),
            ('business_description', _("Business description")),
        ):
            for locale in ('en', 'fr'):
                field = self.fields[f'seo_{stem}_{locale}']
                field.label = format_lazy('{} ({})', label, locale.upper())
                field.help_text = _("Leave blank to use the relevant page or language fallback.")
                if 'description' in stem:
                    field.widget = forms.Textarea(attrs={'rows': 3})
        for name in SEO_FIELDS:
            self.fields[name].help_text = _("Leave blank to use the locale fallback and page defaults. Plain text only.")
        self.fields['seo_theme_color'].widget.attrs['placeholder'] = '#ffffff'
        self.fields['seo_locale_en'].help_text = _("Language and country, for example en_GB.")
        self.fields['seo_locale_fr'].help_text = _("Language and country, for example fr_FR.")
        from .discovery_guidance import apply_guidance
        apply_guidance(self)

    @property
    def groups(self):
        selections = (
            (_("Primary SEO"), ('name', *SEO_FIELDS, 'seo_public_origin', 'seo_home_canonical_en', 'seo_home_canonical_fr', 'seo_robots', 'seo_max_image_preview')),
            (_("Open Graph"), ('seo_social_site_name', 'seo_og_type', 'seo_og_title_en', 'seo_og_title_fr', 'seo_og_description_en', 'seo_og_description_fr', 'seo_og_url_en', 'seo_og_url_fr', 'seo_social_image', 'seo_image_width', 'seo_image_height', 'seo_image_alt_en', 'seo_image_alt_fr', 'seo_locale_en', 'seo_locale_fr')),
            (_("X / Twitter"), ('seo_twitter_card', 'seo_twitter_title_en', 'seo_twitter_title_fr', 'seo_twitter_description_en', 'seo_twitter_description_fr', 'seo_twitter_image')),
            (_("Site identity"), ('seo_favicon', 'seo_apple_icon', 'seo_theme_color')),
            (_("Search engine verification"), ('seo_google_verification', 'seo_bing_verification')),
            (_("Business structured data"), tuple(field for field in DISCOVERY_FIELDS if field.startswith('seo_business_'))),
        )
        return [(title, [self[field] for field in fields]) for title, fields in selections]


class ContactForm(forms.ModelForm):
    version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)

    class Meta:
        model = SiteContent
        fields = ("contact_email", "contact_phone", "contact_address", "contact_intro_en", "contact_intro_fr", "contact_hours_en", "contact_hours_fr")
        labels = {"contact_email": _("Public email address"), "contact_phone": _("Phone number"),
            "contact_address": _("Postal address"), "contact_intro_en": _("Contact introduction (English)"),
            "contact_intro_fr": _("Contact introduction (French)"),
            "contact_hours_en": _("Opening hours (English)"), "contact_hours_fr": _("Opening hours (French)")}
        widgets = {field: forms.Textarea(attrs={"rows": 3}) for field in fields if field not in ("contact_email", "contact_phone")}


class ReviewsForm(forms.ModelForm):
    version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)

    class Meta:
        model = SiteContent
        fields = ("reviews_enabled",)
        labels = {"reviews_enabled": _("Show the reviews page")}
        help_texts = {"reviews_enabled": _("When disabled, Reviews is hidden from navigation and the sitemap, and the public page is unavailable. Existing reviews are retained.")}


class DeleteStoryForm(forms.Form):
    version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    confirm = forms.BooleanField(label=_("I confirm deleting this story from the site."))


class ContactMailForm(forms.Form):
    version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    enabled = forms.BooleanField(required=False, label=_("Enable contact email delivery"))
    host = forms.RegexField(regex=r'^[A-Za-z0-9.-]{1,253}$', required=False, max_length=253,
        label=_("SMTP hostname"), widget=forms.TextInput(attrs={'placeholder':'smtp.example.com'}))
    port = forms.IntegerField(min_value=1, max_value=65535, initial=587, label=_("SMTP port"))
    security = forms.ChoiceField(choices=[('starttls',_('STARTTLS (usually port 587)')), ('ssl',_('SSL/TLS (usually port 465)')), ('none',_('None (local mail server)'))], label=_("Connection security"))
    from_email = forms.EmailField(required=False, label=_("Sender email address"),
        help_text=_("Use an address your email provider permits you to send from."))
    username = forms.CharField(required=False, max_length=254, label=_("SMTP username"),
        widget=forms.TextInput(attrs={'autocomplete':'off'}))
    password = forms.CharField(required=False, max_length=1024, strip=False, label=_("SMTP password or app password"),
        widget=forms.PasswordInput(attrs={'autocomplete':'new-password'}),
        help_text=_("Leave blank to keep the saved password. The saved password is never displayed."))
    clear_password = forms.BooleanField(required=False, label=_("Remove the saved SMTP password"))

    def clean(self):
        data = super().clean()
        if data.get('password') and data.get('clear_password'):
            raise forms.ValidationError(_('Enter a new password or remove the saved password, not both.'))
        if data.get('enabled'):
            for name in ('host', 'from_email'):
                if not data.get(name):
                    self.add_error(name, _('This field is required to enable email delivery.'))
        return data


from domain.content.models import SitePolicy
from domain.content.policy import POLICY_FIELDS


class PolicyForm(forms.ModelForm):
    version = forms.IntegerField(min_value=1, widget=forms.HiddenInput)

    class Meta:
        model = SitePolicy
        fields = POLICY_FIELDS
        labels = {"title":_("Policy title"), "site_name":_("Policy site name"),
            "operator_name":_("Operator or business name"),
            "contact_address":_("Policy contact address"), "updated_on":_("Last updated date"),
            "body":_("Full policy text")}
        widgets = {"body":forms.Textarea(attrs={"rows":32}), "contact_address":forms.Textarea(attrs={"rows":3}),
            "updated_on":forms.DateInput(attrs={"type":"date"}, format="%Y-%m-%d")}
        help_texts = {"body":_("Use blank lines between paragraphs and ## before section headings. The placeholders {site_name}, {operator_name}, {contact_email} and {contact_address} use the details above. HTML is displayed as plain text.")}
