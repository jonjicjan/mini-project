import os
import secrets
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
DEBUG = os.environ.get("REGISTER_ENV", "development") == "development"
DATA_DIR = Path(os.environ.get("REGISTER_DATA_DIR", BASE_DIR / "var")).resolve()
if not DEBUG and not os.environ.get("REGISTER_DATA_DIR"):
    raise ImproperlyConfigured("Production requires an explicit REGISTER_DATA_DIR.")
DATA_DIR.mkdir(parents=True, exist_ok=True)
SECRET_KEY = os.environ.get("REGISTER_SECRET_KEY", "")
if not SECRET_KEY and DEBUG:
    secret_file = DATA_DIR / "development-secret.key"
    try:
        with secret_file.open("x", encoding="utf-8") as stream:
            stream.write(secrets.token_urlsafe(64))
    except FileExistsError:
        pass
    SECRET_KEY = secret_file.read_text(encoding="utf-8").strip()
if len(SECRET_KEY) < 50:
    raise ImproperlyConfigured("REGISTER_SECRET_KEY must contain at least 50 characters.")

ALLOWED_HOSTS = [
    s.strip()
    for s in os.environ.get("REGISTER_ALLOWED_HOSTS", "127.0.0.1,localhost" if DEBUG else "").split(
        ","
    )
    if s.strip()
]
if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
    raise ImproperlyConfigured("Set explicit REGISTER_ALLOWED_HOSTS; wildcards are not allowed.")
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
    "accounts",
    "registers",
    "exports",
    "scheduling",
    "attendance",
    "assessments",
    "operations",
]
MIDDLEWARE = [
    "operations.middleware.MaintenanceMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "accounts.middleware.SessionVersionMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATA_DIR / "register.sqlite3",
        "OPTIONS": {"timeout": 5, "transaction_mode": "IMMEDIATE"},
    }
}
AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = ["accounts.backends.FacultyBackend"]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"
SESSION_COOKIE_AGE = 8 * 60 * 60
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = not DEBUG
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
# Only enable this when a loopback-only server is behind the configured trusted proxy.
if os.environ.get("REGISTER_TRUST_PROXY") == "1":
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
LANGUAGE_CODE = "en-in"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = DATA_DIR / "static"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
DATA_UPLOAD_MAX_MEMORY_SIZE = 1_048_576
