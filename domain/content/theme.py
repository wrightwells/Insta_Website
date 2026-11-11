from django.utils.translation import gettext_lazy as _
import re

from django.core.exceptions import ValidationError

THEME_FIELDS = ("background_color", "text_color", "muted_color", "accent_color", "font")
FONTS = {
    "editorial": ("system-ui, sans-serif", "Georgia, serif"),
    "system": ("system-ui, sans-serif", "system-ui, sans-serif"),
    "serif": ("Georgia, serif", "Georgia, serif"),
}


def _luminance(value: str) -> float:
    channels = [int(value[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    channels = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in channels]
    return sum(c * weight for c, weight in zip(channels, (.2126, .7152, .0722)))


def contrast(a: str, b: str) -> float:
    bright, dark = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (bright + .05) / (dark + .05)


def validate_theme(theme) -> None:
    colors = [theme.background_color, theme.text_color, theme.muted_color, theme.accent_color]
    if any(not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color) for color in colors):
        raise ValidationError(_("Use six-digit hexadecimal colours, such as #253b33."))
    if theme.font not in FONTS:
        raise ValidationError(_("Choose an approved font."))
    for color in colors[1:]:
        if contrast(color, theme.background_color) < 4.5 or contrast(color, "#ffffff") < 4.5:
            raise ValidationError(_("Text, secondary text and accent colours need at least 4.5:1 contrast against the page and white cards."))


def theme_css(theme, *, preview: bool = False, image_url: str = "") -> str:
    validate_theme(theme)
    body_font, heading_font = FONTS[theme.font]
    selector = ".theme-preview" if preview else ":root"
    css = (
        f"{selector}{{--paper:{theme.background_color};--ink:{theme.text_color};"
        f"--muted:{theme.muted_color};--accent:{theme.accent_color};"
        f"font-family:{body_font};color:var(--ink);background-color:var(--paper)}}"
    )
    if preview:
        return css + f".theme-preview h3{{font-family:{heading_font}}}.theme-preview a{{color:var(--accent)}}"
    css += f"h1,.wordmark,.review blockquote{{font-family:{heading_font}}}"
    if image_url:
        css += f'body{{background-image:url("{image_url}");background-size:cover;background-attachment:fixed}}.shell{{background-color:var(--paper)}}'
    return css
