"""Examples and actual blank-field fallbacks for the discovery editor."""
from copy import deepcopy

from django.conf import settings
from django.utils.translation import gettext as _

from web.public.copy import COPY
from web.public.metadata import absolute_url, canonical_url, page_metadata, text_fallback


def apply_guidance(form):
    site = form.instance
    examples = {
        'name': 'Fieldnotes', 'seo_public_origin': 'https://yourbrand.com',
        'seo_home_canonical_en': 'https://yourbrand.com/en/', 'seo_home_canonical_fr': 'https://yourbrand.com/fr/',
        'seo_robots': 'Deployment default', 'seo_max_image_preview': 'large', 'seo_social_site_name': 'Fieldnotes',
        'seo_og_type': 'website', 'seo_social_image': 'https://yourbrand.com/images/cover.jpg',
        'seo_image_width': '1200', 'seo_image_height': '630', 'seo_locale_en': 'en_GB', 'seo_locale_fr': 'fr_FR',
        'seo_twitter_card': 'Automatic', 'seo_twitter_image': 'https://yourbrand.com/images/social.jpg',
        'seo_favicon': '/favicon.ico', 'seo_apple_icon': '/apple-touch-icon.png', 'seo_theme_color': '#ffffff',
        'seo_google_verification': 'AbCdEf123_google_token', 'seo_bing_verification': 'ABCDEF0123456789',
        'seo_business_enabled': _('Enable after entering your real business details'),
        'seo_business_type': 'HomeAndConstructionBusiness', 'seo_business_id': 'https://yourbrand.com/#business',
        'seo_business_name': 'Fieldnotes Design', 'seo_business_url': 'https://yourbrand.com/',
        'seo_business_image': 'https://yourbrand.com/images/studio.jpg', 'seo_business_price_range': '££',
        'seo_business_street': '10 Example Street', 'seo_business_town': 'London',
        'seo_business_postcode': 'SW1A 1AA', 'seo_business_country': 'GB', 'seo_business_area_served': 'United Kingdom',
    }
    rules = {
        'name': _('Required. There is no blank fallback.'),
        'seo_public_origin': _('Uses the configured public website origin; omitted if none is configured.'),
        'seo_home_canonical_en': _('Uses the public origin followed by /en/.'),
        'seo_home_canonical_fr': _('Uses the public origin followed by /fr/.'),
        'seo_robots': _('Deployment default follows the indexing configuration. Local and private pages always remain noindex.'),
        'seo_max_image_preview': _('Omitted; the search engine chooses its default image preview.'),
        'seo_social_site_name': _('Uses the site name.'),
        'seo_og_type': _('Required. The initial default is website.'),
        'seo_social_image': _('Uses the first image on the current feed page; omitted on other pages without an image.'),
        'seo_image_width': _('Required. The initial default is 1200 pixels; enter the actual image width.'),
        'seo_image_height': _('Required. The initial default is 630 pixels; enter the actual image height.'),
        'seo_locale_en': _('Required. The initial default is en_GB.'),
        'seo_locale_fr': _('Required. The initial default is fr_FR.'),
        'seo_twitter_card': _('Automatic chooses a large image card when an image exists, otherwise a summary card.'),
        'seo_twitter_image': _('Uses the default social image, then the first feed image; omitted if neither exists.'),
        'seo_favicon': _('No icon link is added. The browser may still request /favicon.ico.'),
        'seo_apple_icon': _('No Apple touch icon link is added.'),
        'seo_theme_color': _('No browser theme colour is added.'),
        'seo_google_verification': _('No Google verification tag is added.'),
        'seo_bing_verification': _('No Bing verification tag is added.'),
        'seo_business_enabled': _('Unchecked: no business structured data is published.'),
        'seo_business_type': _('Required. The initial default is HomeAndConstructionBusiness.'),
        'seo_business_id': _('Uses the business website URL followed by #business.'),
        'seo_business_name': _('No name fallback. A real business name is required when business structured data is enabled.'),
        'seo_business_url': _('Uses the public website origin.'),
        'seo_business_image': _('Uses the default social image; omitted if none is configured.'),
        'seo_business_price_range': _('Omitted from business structured data.'),
        'seo_business_street': _('No address fallback. Required when business structured data is enabled.'),
        'seo_business_town': _('No town fallback. Required when business structured data is enabled.'),
        'seo_business_postcode': _('No postcode fallback. Required when business structured data is enabled.'),
        'seo_business_country': _('Required. The initial default is GB.'),
        'seo_business_area_served': _('Omitted from business structured data.'),
    }
    resolved = {
        'seo_public_origin': settings.PUBLIC_ORIGIN,
        'seo_home_canonical_en': absolute_url('/en/', site), 'seo_home_canonical_fr': absolute_url('/fr/', site),
        'seo_social_site_name': site.name,
        'seo_business_url': absolute_url('/', site), 'seo_business_image': site.seo_social_image,
    }
    business_url = site.seo_business_url or absolute_url('/', site)
    resolved['seo_business_id'] = business_url.split('#')[0] + '#business' if business_url else ''
    for page in ('feed', 'reviews', 'contact'):
        for locale in ('en', 'fr'):
            for stem, example in (('title', COPY[locale][page] + ' · Fieldnotes'),
                                  ('description', _('Discover our latest projects and get in touch.'))):
                name = f'seo_{page}_{stem}_{locale}'
                examples[name] = example
                rules[name] = (_('Uses the other language if supplied, then the page name and site name.') if stem == 'title'
                    else _('Uses the other language if supplied, then the site introduction, then the page title.'))
                candidate = deepcopy(site)
                setattr(candidate, name, '')
                resolved[name] = page_metadata(candidate, locale, page)[stem]
    for locale in ('en', 'fr'):
        for stem, example in (
            ('og_title', 'Fieldnotes — Our latest stories'), ('og_description', _('Projects, stories and inspiration from Fieldnotes.')),
            ('og_url', f'https://yourbrand.com/{locale}/'), ('image_alt', _('A bright living room designed by Fieldnotes')),
            ('twitter_title', 'Fieldnotes — Latest projects'), ('twitter_description', _('See our latest projects and stories.')),
            ('business_description', _('Interior design and renovation services.')),
        ):
            name = f'seo_{stem}_{locale}'
            examples[name] = example
            candidate = deepcopy(site)
            setattr(candidate, name, '')
            metadata = page_metadata(candidate, locale, 'feed')
            if stem in ('og_title', 'og_description', 'twitter_title', 'twitter_description'):
                rules[name] = _('Uses the other language if supplied, then each page’s own title or description.')
                resolved[name] = metadata[stem]
            elif stem == 'og_url':
                rules[name] = _('Uses the homepage canonical URL. Other pages always use their own canonical URL.')
                resolved[name] = canonical_url(candidate, locale, 'feed')
            else:
                rules[name] = _('Uses the other language if supplied; omitted if both languages are blank.')
                resolved[name] = text_fallback(candidate, 'seo_'+stem, locale)
    for name, field in form.fields.items():
        if name == 'version':
            continue
        field.example = examples[name]
        field.fallback = rules[name]
        field.fallback_value = resolved.get(name, '')
        if not field.widget.is_hidden and getattr(field.widget, 'input_type', '') not in ('checkbox', 'select'):
            field.widget.attrs['placeholder'] = examples[name]
