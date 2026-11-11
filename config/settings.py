"""Runtime settings. SQLite and insecure cookies require explicit local mode."""

import os
import re
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from .origin import public_origin
from .mount import script_prefix

BASE_DIR = Path(__file__).resolve().parent.parent
LOCAL = os.environ.get("APP_LOCAL") == "1"
DEBUG = False
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "local-development-only" if LOCAL else "")
if not SECRET_KEY or (not LOCAL and len(SECRET_KEY) < 50):
    raise ImproperlyConfigured("Supply a runtime DJANGO_SECRET_KEY of at least 50 characters.")
RUNTIME = os.environ.get("APP_RUNTIME", "public")
if RUNTIME not in {"public", "admin", "migration"}:
    raise ImproperlyConfigured("APP_RUNTIME must be public, admin or migration.")
if RUNTIME == "admin" and not LOCAL:
    raise ImproperlyConfigured("Administration remains local-only pending independent security and deployment review.")
ADMIN_SLUG = os.environ.get("ADMIN_SLUG", "manage-local" if LOCAL else "")
if RUNTIME == "admin" and not re.fullmatch(r"manage-[a-zA-Z0-9-]{4,80}", ADMIN_SLUG):
    raise ImproperlyConfigured("Set ADMIN_SLUG to manage- followed by 4–80 letters/digits/hyphens.")
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]" if LOCAL else "").split(",")
APP_SCRIPT_PREFIX = script_prefix(os.environ.get("APP_SCRIPT_PREFIX", ""))
if APP_SCRIPT_PREFIX and RUNTIME != "public":
    raise ImproperlyConfigured("APP_SCRIPT_PREFIX currently supports only the public runtime.")
ROOT_URLCONF = "web.administration.urls" if RUNTIME == "admin" else "web.public.prefixed_urls" if APP_SCRIPT_PREFIX else "web.public.urls"
WSGI_APPLICATION = "config.wsgi.application"

INSTALLED_APPS = [
    "web.public",
    "django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions",
    "django.contrib.messages", "django.contrib.staticfiles", "domain.content",
]
if RUNTIME in {"admin", "migration"}:
    INSTALLED_APPS.append("web.administration")
if RUNTIME == "migration":
    INSTALLED_APPS.append("django.contrib.admin")
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "web.public.middleware.SecurityHeadersMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
PUBLIC_MIDDLEWARE = MIDDLEWARE.copy()
if RUNTIME in {"admin", "migration"}:
    MIDDLEWARE[2:2] = ["django.contrib.sessions.middleware.SessionMiddleware"]
    MIDDLEWARE.insert(3, "web.administration.locales.AdminLocaleMiddleware")
    MIDDLEWARE[-1:-1] = [
        "django.contrib.auth.middleware.AuthenticationMiddleware",
        "django.contrib.messages.middleware.MessageMiddleware",
    ]
    MIDDLEWARE.insert(MIDDLEWARE.index("django.contrib.auth.middleware.AuthenticationMiddleware") + 1, "web.administration.security.OwnerSessionMiddleware")
    MIDDLEWARE.insert(MIDDLEWARE.index("web.administration.security.OwnerSessionMiddleware") + 1, "web.administration.upload_guard.UploadGuardMiddleware")
CONTEXT_PROCESSORS = ["django.template.context_processors.request"]
if RUNTIME in {"admin", "migration"}:
    CONTEXT_PROCESSORS += [
        "web.administration.locales.administration_context",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [], "APP_DIRS": True,
    "OPTIONS": {"context_processors": CONTEXT_PROCESSORS},
}]

if os.environ.get("POSTGRES_HOST"):
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": os.environ["POSTGRES_HOST"],
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        "NAME": os.environ.get("POSTGRES_DB", "instagram"),
        "USER": os.environ["POSTGRES_USER"],
        "PASSWORD": os.environ["POSTGRES_PASSWORD"],
        "CONN_MAX_AGE": 60, "OPTIONS": {"connect_timeout": 3},
    }}
elif LOCAL:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "local.sqlite3"}}
else:
    raise ImproperlyConfigured("PostgreSQL is required outside explicit APP_LOCAL=1 mode.")

PASSWORD_HASHERS = ["django.contrib.auth.hashers.Argon2PasswordHasher"]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 14}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "en"
LANGUAGES = [("en", "English"), ("fr", "Français")]
TIME_ZONE = "Europe/London"
USE_I18N = True
LOCALE_PATHS = [BASE_DIR / "locales"]
USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
STATIC_URL = APP_SCRIPT_PREFIX + "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
# This directory is never mounted as a public/static URL.
PRIVATE_MEDIA_ROOT = Path(os.environ.get("PRIVATE_MEDIA_ROOT", BASE_DIR / "private-media"))
SESSION_COOKIE_NAME = "instagram_admin_session"
SESSION_COOKIE_SECURE = not LOCAL
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict"
SESSION_COOKIE_AGE = 1800
SESSION_SAVE_EVERY_REQUEST = True
CSRF_COOKIE_SECURE = not LOCAL
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SAMESITE = "Strict"
SECURE_SSL_REDIRECT = not LOCAL
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
# Enable only when the owner proxy strips client-supplied forwarding headers.
if os.environ.get("TRUST_HTTPS_PROXY") == "1":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
CSRF_TRUSTED_ORIGINS = list(filter(None, os.environ.get("CSRF_TRUSTED_ORIGINS", "").split(",")))
DATA_UPLOAD_MAX_MEMORY_SIZE = 64 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FILES = 1
FILE_UPLOAD_HANDLERS = [
    "web.administration.upload_guard.BoundedImageUploadHandler",
    "django.core.files.uploadhandler.MemoryFileUploadHandler",
    "django.core.files.uploadhandler.TemporaryFileUploadHandler",
]
MEDIA_STORAGE_LIMIT_BYTES = int(os.environ.get("MEDIA_STORAGE_LIMIT_BYTES", str(512 * 1024 * 1024)))
if MEDIA_STORAGE_LIMIT_BYTES < 1:
    raise ImproperlyConfigured("MEDIA_STORAGE_LIMIT_BYTES must be positive.")
LANGUAGE_COOKIE_NAME = os.environ.get("LANGUAGE_COOKIE_NAME", "site_language")

# Explicit operator configuration; request Host/forwarding headers never set canonicals.
PUBLIC_ORIGIN = public_origin(os.environ.get("PUBLIC_ORIGIN", "http://localhost:8000" if LOCAL else ""), local=LOCAL)
PUBLIC_INDEXING_ENABLED = os.environ.get("PUBLIC_INDEXING_ENABLED") == "1"
if PUBLIC_INDEXING_ENABLED and (LOCAL or not PUBLIC_ORIGIN):
    raise ImproperlyConfigured("Public indexing requires non-local mode and a configured HTTPS PUBLIC_ORIGIN.")

LANGUAGE_COOKIE_PATH = APP_SCRIPT_PREFIX + "/" if APP_SCRIPT_PREFIX else "/"
LANGUAGE_COOKIE_SECURE = os.environ.get("LANGUAGE_COOKIE_SECURE", "0" if LOCAL else "1") == "1"

# Owner application controls an isolated Instagram agent; public runtime never
# reads the control capability or Instagram credentials.
INSTAGRAM_AGENT_URL = os.environ.get("INSTAGRAM_AGENT_URL", "http://127.0.0.1:8769")
INSTAGRAM_CONTROL_KEY_FILE = os.environ.get("INSTAGRAM_CONTROL_KEY_FILE", str(Path.home() / ".local/share/mysite-instagram-control/control.key"))

# Credentials live outside source/static mounts in a private shared directory.
CONTACT_MAIL_SETTINGS_FILE = os.environ.get('CONTACT_MAIL_SETTINGS_FILE', str(Path.home() / '.local/share/fieldnotes-mail/smtp.json'))
CONTACT_EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

POLICY_EXPORT_FILE = os.environ.get('POLICY_EXPORT_FILE', str(Path.home() / '.local/share/fieldnotes-policy/privacy.html'))
