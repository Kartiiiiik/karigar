"""
Base settings shared by every environment.

Environment-specific overrides live in ``dev.py`` and ``prod.py``.
All secrets and environment-specific values are read from the environment
via ``django-environ`` so nothing sensitive is ever committed.
"""
from datetime import timedelta
from pathlib import Path

import environ
from celery.schedules import crontab

# backend/config/settings/base.py -> parents[2] == backend/
BASE_DIR = Path(__file__).resolve().parents[2]

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, ["localhost", "127.0.0.1"]),
    DJANGO_CORS_ALLOWED_ORIGINS=(list, ["http://localhost:5173"]),
    USE_SQLITE=(bool, False),
)

# Read a .env file if present (repo root or backend/).
for candidate in (BASE_DIR.parent / ".env", BASE_DIR / ".env"):
    if candidate.exists():
        environ.Env.read_env(str(candidate))
        break

# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
SECRET_KEY = env("DJANGO_SECRET_KEY", default="dev-insecure-change-me")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third party
    "corsheaders",
    "simple_history",
    "django_celery_beat",
    # Local
    "apps.common",
    "apps.accounts",
    "apps.ledger",
    "apps.reports",
    "apps.backups",
    "apps.bandaki",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
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
if env("USE_SQLITE"):
    # Local development convenience only. NEVER used in production.
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": env.db(
            "DATABASE_URL",
            default="postgres://karigar:karigar@localhost:5432/karigar",
        )
    }
    DATABASES["default"].setdefault("CONN_MAX_AGE", 60)

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Internationalisation / time
# ---------------------------------------------------------------------------
# Store everything in Asia/Kathmandu (UTC+05:45). BS is derived at display time;
# it is never the source of truth in the database.
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kathmandu"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static / media
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Django Ninja + JWT
# ---------------------------------------------------------------------------
# The API is built with Django Ninja (Pydantic schemas), not DRF. JWT auth is
# provided by django-ninja-jwt.
NINJA_PAGINATION_PER_PAGE = 25
NINJA_PAGINATION_MAX_LIMIT = 200

NINJA_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": False,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "TOKEN_OBTAIN_SERIALIZER": "ninja_jwt.schema.TokenObtainPairInputSchema",
}

# Login throttle rate (requests/duration) applied to the auth endpoints.
AUTH_THROTTLE_RATE = "10/min"

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env("DJANGO_CORS_ALLOWED_ORIGINS")
CORS_ALLOW_CREDENTIALS = True

# ---------------------------------------------------------------------------
# Celery
# ---------------------------------------------------------------------------
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="redis://localhost:6379/1")
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=False)
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True

# Beat schedule: check daily for backup configs that are due (each config's own
# weekly/monthly frequency gates whether it actually runs).
CELERY_BEAT_SCHEDULE = {
    "run-scheduled-backups-daily": {
        "task": "apps.backups.tasks.run_scheduled_backups",
        "schedule": crontab(hour=2, minute=0),
    },
}

# ---------------------------------------------------------------------------
# Email (used by backups)
# ---------------------------------------------------------------------------
EMAIL_BACKEND = env(
    "DJANGO_EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend",
)
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="no-reply@karigar.local")

# ---------------------------------------------------------------------------
# App-specific domain constants
# ---------------------------------------------------------------------------
# Gold purity: net_weight = gross_weight * (carat / 24). 22kt uses 22/24 exactly.
GOLD_PURE_CARAT = 24

# ---------------------------------------------------------------------------
# Backups (resilient, off-Docker-volume)
# ---------------------------------------------------------------------------
# Master key for encrypting backup files (urlsafe base64 Fernet key). MUST come
# from the environment / a secrets manager — never committed, never emailed,
# never stored in the DB. A dev fallback is generated so local runs work.
BACKUP_ENCRYPTION_KEY = env("BACKUP_ENCRYPTION_KEY", default="")

# Default destination paths (bind-mounted host folders — NOT Docker volumes).
# These are container paths; the frontend lets staff type Windows host paths,
# which are resolved to container mounts via BACKUP_PATH_MAP below.
BACKUP_PRIMARY_PATH = env("BACKUP_PRIMARY_PATH", default=str(BASE_DIR / "backups"))
BACKUP_SECONDARY_PATH = env("BACKUP_SECONDARY_PATH", default="")

# Maps host path prefixes (as staff would type them, e.g. "D:\\SecureBackups")
# to the container mount point they are bind-mounted at. Lets a Windows-style
# path entered in the UI resolve to where the container can actually write.
# JSON object, e.g. {"D:\\\\SecureBackups": "/app/backups", "E:": "/app/backups-secondary"}
BACKUP_PATH_MAP = env.json("BACKUP_PATH_MAP", default={})

# App version stamped into each backup manifest (set at deploy time).
APP_GIT_SHA = env("APP_GIT_SHA", default="dev")

# pg_dump / pg_restore binaries (overridable if not on PATH).
PG_DUMP_BIN = env("PG_DUMP_BIN", default="pg_dump")
PG_RESTORE_BIN = env("PG_RESTORE_BIN", default="pg_restore")

# ---------------------------------------------------------------------------
# Logging (structured, console-based; prod adds handlers)
# ---------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
        "apps": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}
