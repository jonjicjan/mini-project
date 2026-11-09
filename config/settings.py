import os
import secrets
from pathlib import Path
from urllib.parse import unquote, urlsplit

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# Load local .env file if present
env_file = BASE_DIR / ".env"
if env_file.exists():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip().strip("'\""))

# Production and Debug detection
is_render = "RENDER" in os.environ
is_production = os.environ.get("REGISTER_ENV") == "production" or is_render
DEBUG = not is_production and os.environ.get("REGISTER_ENV", "development") == "development"

DATA_DIR = Path(os.environ.get("REGISTER_DATA_DIR", BASE_DIR / "var")).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)

SECRET_KEY = os.environ.get("REGISTER_SECRET_KEY", "")
if not SECRET_KEY:
    secret_file = DATA_DIR / ("development-secret.key" if DEBUG else "production-secret.key")
    try:
        with secret_file.open("x", encoding="utf-8") as stream:
            stream.write(secrets.token_urlsafe(64))
    except FileExistsError:
        pass
    SECRET_KEY = secret_file.read_text(encoding="utf-8").strip()

# Base allowed hosts
ALLOWED_HOSTS = [
    "127.0.0.1",
    "localhost",
    "mini-project-2-7lhe.onrender.com",
]

# Additional allowed hosts from environment
extra_hosts = [
    s.strip()
    for s in os.environ.get("REGISTER_ALLOWED_HOSTS", "").split(",")
    if s.strip()
]
for host in extra_hosts:
    if host not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(host)

# Automatically add Render's assigned external hostname
render_hostname = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
if render_hostname and render_hostname not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(render_hostname)

# CSRF Trusted Origins for secure HTTPS form submissions
CSRF_TRUSTED_ORIGINS = [
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "https://mini-project-2-7lhe.onrender.com",
]

extra_csrf = [
    s.strip()
    for s in os.environ.get("REGISTER_CSRF_TRUSTED_ORIGINS", "").split(",")
    if s.strip()
]
for origin in extra_csrf:
    if origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(origin)

if render_hostname:
    render_origin = f"https://{render_hostname}"
    if render_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(render_origin)

if not DEBUG:
    for h in ALLOWED_HOSTS:
        if h and not h.startswith(".") and not h.startswith("127.") and h != "localhost":
            origin = f"https://{h}"
            if origin not in CSRF_TRUSTED_ORIGINS:
                CSRF_TRUSTED_ORIGINS.append(origin)
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
    "whitenoise.middleware.WhiteNoiseMiddleware",
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
# REGISTER_DATABASE_URL or DATABASE_URL selects a PostgreSQL server (e.g. Supabase).
# Without it, the installation keeps its self-contained SQLite file at DATA_DIR/register.sqlite3.
DATABASE_URL = (
    os.environ.get("DATABASE_URL")
    or os.environ.get("REGISTER_DATABASE_URL")
    or ""
).strip()

if DATABASE_URL:
    is_postgres = DATABASE_URL.startswith("postgres://") or DATABASE_URL.startswith("postgresql://")
    DATABASES = {
        "default": dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
            ssl_require=is_postgres and ("supabase" in DATABASE_URL or "pooler" in DATABASE_URL or not DEBUG),
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": DATA_DIR / "register.sqlite3",
            "OPTIONS": {"timeout": 5, "transaction_mode": "IMMEDIATE"},
        }
    }

# Supabase API credentials
SUPABASE_URL = os.environ.get("SUPABASE_URL", os.environ.get("NEXT_PUBLIC_SUPABASE_URL", ""))
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", os.environ.get("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY", ""))
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
SECURE_REDIRECT_EXEMPT = [r"^health/?$"]
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG
# Enable proxy SSL header when behind Render or configured reverse proxy
if os.environ.get("REGISTER_TRUST_PROXY") == "1" or is_render:
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
