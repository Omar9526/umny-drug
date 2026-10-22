"""
Django settings for the «Умный друг» backend.

All configuration comes from environment variables (see ../.env.example).
Two profiles:
  * production / docker compose: PostgreSQL + Redis + S3-compatible storage + Celery workers;
  * DEV_FALLBACK=1: SQLite + eager Celery + local cache + private local file storage.
    The dev fallback exists only for machines without Docker/PostgreSQL and is refused
    when ENVIRONMENT=production.
"""

from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR.parent / ".env")
load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


DEV_FALLBACK = env_bool("DEV_FALLBACK", False)
# Fail closed: a deployment that forgets ENVIRONMENT gets production guards (no DEBUG, real SECRET_KEY),
# not a debug server. Local work sets ENVIRONMENT=development (or DEV_FALLBACK=1) in .env.
ENVIRONMENT = os.getenv("ENVIRONMENT") or ("development" if DEV_FALLBACK else "production")
DEBUG = env_bool("DJANGO_DEBUG", ENVIRONMENT == "development")

_PLACEHOLDER_SECRETS = {
    "",
    "change-me",
    "change-me-to-a-long-random-string",
    "dev-only-insecure-secret-key-change-me",
}
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if not DEBUG and (SECRET_KEY in _PLACEHOLDER_SECRETS or len(SECRET_KEY) < 50):
    raise RuntimeError(
        "DJANGO_SECRET_KEY must be a unique random string of at least 50 characters when DEBUG is off"
    )
if not SECRET_KEY:
    SECRET_KEY = "dev-only-insecure-secret-key-change-me"

if ENVIRONMENT == "production" and DEV_FALLBACK:
    raise RuntimeError("DEV_FALLBACK cannot be enabled in production")
if ENVIRONMENT == "production" and DEBUG:
    raise RuntimeError("DJANGO_DEBUG must be off in production")

ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS", "")

# Number of trusted reverse proxies in front of Django. 0 = trust only REMOTE_ADDR (never the
# client-controlled X-Forwarded-For). Used by DRF throttling and by apps.core.network.client_ip.
NUM_PROXIES = int(os.getenv("NUM_PROXIES", "0"))

# Django admin lives on a path taken from the environment so it is not trivially discoverable.
ADMIN_URL_PATH = os.getenv("DJANGO_ADMIN_PATH", "admin/").strip("/") + "/"

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django_otp",
    "django_otp.plugins.otp_totp",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    # third-party
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "drf_spectacular",
    "corsheaders",
    "django_filters",
    # project
    "apps.core",
    "apps.accounts",
    "apps.curriculum",
    "apps.assignments",
    "apps.tutor",
    "apps.learning",
    "apps.quizzes",
    "apps.parents",
    "apps.billing",
]

MIDDLEWARE = [
    "apps.core.middleware.RequestIdMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django_otp.middleware.OTPMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
if DEV_FALLBACK:
    _default_db_url = "sqlite:///" + str(BASE_DIR / "db.sqlite3")
else:
    _default_db_url = "postgres://umnydrug:umnydrug@localhost:5432/umnydrug"

DATABASES = {
    "default": dj_database_url.config(
        default=os.getenv("DATABASE_URL", _default_db_url),
        conn_max_age=60,
    )
}
if DATABASES["default"]["ENGINE"].endswith("sqlite3"):
    # Dev fallback only: concurrent writers (E2E, eager Celery) wait instead of failing with «locked».
    DATABASES["default"].setdefault("OPTIONS", {})["timeout"] = 30  # sqlite_timeout
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Cache / Celery
# ---------------------------------------------------------------------------
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

if DEV_FALLBACK:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "umnydrug",
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
        }
    }

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", REDIS_URL)
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", REDIS_URL)
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", DEV_FALLBACK)
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_TIME_LIMIT = 180
CELERY_TASK_SOFT_TIME_LIMIT = 150
CELERY_TIMEZONE = "Asia/Bishkek"

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Production defaults; a local .env may relax them (e.g. for repeated E2E runs). Tests always use these.
THROTTLE_DEFAULTS = {
    "anon": "60/min",
    "user": "300/min",
    "auth": "10/min",
    "child_login": "8/min",
    "refresh": "30/min",
    "upload": "20/hour",
    "ai": "60/hour",
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ("rest_framework_simplejwt.authentication.JWTAuthentication",),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_PAGINATION_CLASS": "apps.core.pagination.DefaultPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": ("django_filters.rest_framework.DjangoFilterBackend",),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "NUM_PROXIES": NUM_PROXIES,
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        scope: os.getenv(f"THROTTLE_{scope.upper()}", rate) for scope, rate in THROTTLE_DEFAULTS.items()
    },
    "EXCEPTION_HANDLER": "apps.core.exceptions.api_exception_handler",
    "DEFAULT_RENDERER_CLASSES": ("rest_framework.renderers.JSONRenderer",)
    + (("rest_framework.renderers.BrowsableAPIRenderer",) if DEBUG else ()),
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(os.getenv("JWT_ACCESS_MINUTES", "15"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(os.getenv("JWT_REFRESH_DAYS", "30"))),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    # A dedicated signing key keeps JWTs valid across SECRET_KEY rotations and vice versa.
    "SIGNING_KEY": os.getenv("JWT_SIGNING_KEY") or SECRET_KEY,
}

# The refresh token travels in an HttpOnly cookie; the access token lives in client memory only.
AUTH_COOKIE_NAME = "ud_refresh"
AUTH_COOKIE_SECURE = env_bool("AUTH_COOKIE_SECURE", ENVIRONMENT == "production")
AUTH_COOKIE_SAMESITE = os.getenv("AUTH_COOKIE_SAMESITE", "Lax")
AUTH_COOKIE_DOMAIN = os.getenv("AUTH_COOKIE_DOMAIN") or None
AUTH_COOKIE_PATH = "/api/v1/auth/"
if AUTH_COOKIE_SAMESITE not in {"Lax", "Strict", "None"}:
    raise RuntimeError("AUTH_COOKIE_SAMESITE must be Lax, Strict or None")
if AUTH_COOKIE_SAMESITE == "None" and not AUTH_COOKIE_SECURE:
    raise RuntimeError("AUTH_COOKIE_SAMESITE=None requires AUTH_COOKIE_SECURE=1")

SPECTACULAR_SETTINGS = {
    "TITLE": "Умный друг API",
    "DESCRIPTION": "Образовательный помощник для школьников и родителей.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
    "SCHEMA_PATH_PREFIX": r"/api/v1",
    "SERVE_PERMISSIONS": ["rest_framework.permissions.AllowAny"]
    if DEBUG
    else ["apps.core.permissions.IsAdminRole"],
}

CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
CORS_ALLOW_CREDENTIALS = True

# ---------------------------------------------------------------------------
# Child-safety / data-retention policy
# ---------------------------------------------------------------------------
CHILD_PIN_MAX_ATTEMPTS = int(os.getenv("CHILD_PIN_MAX_ATTEMPTS", "5"))
CHILD_PIN_LOCK_MINUTES = int(os.getenv("CHILD_PIN_LOCK_MINUTES", "15"))
CHILD_PIN_MAX_LOCKOUTS = int(os.getenv("CHILD_PIN_MAX_LOCKOUTS", "3"))
ASSIGNMENT_IMAGE_RETENTION_DAYS = int(os.getenv("ASSIGNMENT_IMAGE_RETENTION_DAYS", "30"))
MAX_UPLOAD_IMAGE_MB = int(os.getenv("MAX_UPLOAD_IMAGE_MB", "10"))
MAX_UPLOAD_IMAGES_PER_ASSIGNMENT = int(os.getenv("MAX_UPLOAD_IMAGES_PER_ASSIGNMENT", "5"))
DATA_UPLOAD_MAX_MEMORY_SIZE = (MAX_UPLOAD_IMAGE_MB * MAX_UPLOAD_IMAGES_PER_ASSIGNMENT + 2) * 1024 * 1024
# Multipart file parts are not counted by DATA_UPLOAD_MAX_MEMORY_SIZE; cap their number here and the
# total body size on the reverse proxy (see deployment notes in README).
DATA_UPLOAD_MAX_NUMBER_FILES = MAX_UPLOAD_IMAGES_PER_ASSIGNMENT
MAX_IMAGE_PIXELS = int(os.getenv("MAX_IMAGE_PIXELS", "40000000"))
CONSENT_TERMS_VERSION = os.getenv("CONSENT_TERMS_VERSION", "2026-10-01")

# ---------------------------------------------------------------------------
# AI provider
# ---------------------------------------------------------------------------
AI_PROVIDER = os.getenv("AI_PROVIDER", "auto")  # auto | anthropic | gemini | demo
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
# 3.5 Flash: ~3 s to first token and stable; 3.8 Flash is cheaper but slower and often 503 (Oct 2026).
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
# Recognition (OCR + segmentation) is latency-critical: the lite model answers in ~2 s vs 15–25 s.
GEMINI_MODEL_VISION = os.getenv("GEMINI_MODEL_VISION", "gemini-3.5-flash-lite")
GEMINI_THINKING_LEVEL = os.getenv("GEMINI_THINKING_LEVEL", "low")  # minimal | low | medium | high
AI_MODEL_VISION = os.getenv("AI_MODEL_VISION", "claude-opus-5-5")
AI_MODEL_TUTOR = os.getenv("AI_MODEL_TUTOR", "claude-opus-5-5")
AI_MODEL_VERIFY = os.getenv("AI_MODEL_VERIFY", "claude-opus-5-5")
AI_REQUEST_TIMEOUT_SECONDS = int(os.getenv("AI_REQUEST_TIMEOUT_SECONDS", "90"))
AI_MAX_OUTPUT_TOKENS = int(os.getenv("AI_MAX_OUTPUT_TOKENS", "4096"))
AI_DAILY_BUDGET_USD = float(os.getenv("AI_DAILY_BUDGET_USD", "25"))
AI_DAILY_BUDGET_PER_FAMILY_USD = float(os.getenv("AI_DAILY_BUDGET_PER_FAMILY_USD", "2"))
AI_DAILY_CALLS_PER_STUDENT = int(os.getenv("AI_DAILY_CALLS_PER_STUDENT", "150"))
AI_PRICING_JSON = os.getenv(
    "AI_PRICING_JSON", ""
)  # {"model": {"input":..,"output":..,"cache_read":..,"cache_write":..}} per MTok
AI_HISTORY_TURNS = int(os.getenv("AI_HISTORY_TURNS", "24"))

# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATIC_ROOT.mkdir(parents=True, exist_ok=True)
WHITENOISE_USE_FINDERS = DEBUG
WHITENOISE_AUTOREFRESH = DEBUG
PRIVATE_MEDIA_ROOT = Path(os.getenv("PRIVATE_MEDIA_ROOT", str(BASE_DIR / "private_media")))

STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local" if DEV_FALLBACK else "s3")
if STORAGE_BACKEND == "s3":
    _private_storage = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": os.getenv("S3_BUCKET", "umnydrug-private"),
            "access_key": os.getenv("S3_ACCESS_KEY", ""),
            "secret_key": os.getenv("S3_SECRET_KEY", ""),
            "endpoint_url": os.getenv("S3_ENDPOINT_URL") or None,
            "region_name": os.getenv("S3_REGION", "us-east-1"),
            "default_acl": "private",
            "querystring_auth": True,
            "querystring_expire": 600,
            "file_overwrite": False,
        },
    }
else:
    _private_storage = {
        "BACKEND": "apps.core.storage.PrivateFileSystemStorage",
        "OPTIONS": {"location": str(PRIVATE_MEDIA_ROOT)},
    }

STORAGES = {
    "default": _private_storage,
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

# ---------------------------------------------------------------------------
# i18n
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "ru"
LANGUAGES = [("ru", "Русский"), ("ky", "Кыргызча")]
TIME_ZONE = "Asia/Bishkek"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Security headers
# ---------------------------------------------------------------------------
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") if NUM_PROXIES > 0 else None
SESSION_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
if ENVIRONMENT == "production":
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(
        os.getenv("SECURE_HSTS_SECONDS", str(60 * 60 * 24 * 180))
    )  # same as next.config
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", False)  # only after a year-long max-age

# ---------------------------------------------------------------------------
# Logging (structured, no PII)
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Email and operations alerts
# ---------------------------------------------------------------------------
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend"
    if ENVIRONMENT == "development"
    else "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "Умный друг <no-reply@umnydrug.local>")
SERVER_EMAIL = os.getenv("SERVER_EMAIL", DEFAULT_FROM_EMAIL)
# Who receives operational alerts (AI budget, errors): "ops@example.com,admin@example.com".
ADMINS = [(address.split("@")[0], address) for address in env_list("DJANGO_ADMINS", "")]
if ENVIRONMENT == "production" and (not ADMINS or not EMAIL_HOST):
    import warnings

    warnings.warn(
        "DJANGO_ADMINS/EMAIL_HOST are not set: AI budget alerts and error mails have nowhere to go",
        RuntimeWarning,
        stacklevel=1,
    )
# Alert when today's AI spend crosses this share of AI_DAILY_BUDGET_USD (checked by a beat task).
AI_BUDGET_ALERT_THRESHOLD = float(os.getenv("AI_BUDGET_ALERT_THRESHOLD", "0.8"))
# A rotated refresh token presented again within this window is a tab race, not a stolen cookie.
AUTH_REFRESH_REUSE_GRACE_SECONDS = int(os.getenv("AUTH_REFRESH_REUSE_GRACE_SECONDS", "30"))
# Label shown in authenticator apps for the admin 2FA entry.
OTP_TOTP_ISSUER = "Умный друг"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"request_id": {"()": "apps.core.logging.RequestIdFilter"}},
    "formatters": {
        "json": {"()": "apps.core.logging.JsonFormatter"},
        "plain": {"format": "%(levelname)s %(asctime)s [%(request_id)s] %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["request_id"],
            "formatter": "plain" if DEBUG else "json",
        }
    },
    "root": {"handlers": ["console"], "level": os.getenv("LOG_LEVEL", "INFO")},
    "loggers": {
        "django.request": {"level": "WARNING", "propagate": True},
        "umnydrug": {"level": os.getenv("LOG_LEVEL", "INFO"), "propagate": True},
    },
}
