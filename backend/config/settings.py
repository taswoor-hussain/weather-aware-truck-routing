import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DEBUG = os.environ.get("DJANGO_DEBUG", "false").lower() == "true"
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "local-development-only" if DEBUG else "")
ALLOWED_HOSTS = os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
if railway_domain := os.environ.get("RAILWAY_PUBLIC_DOMAIN"):
    ALLOWED_HOSTS.append(railway_domain)
    # Railway's health checks arrive with this host header.
    ALLOWED_HOSTS.append("healthcheck.railway.app")

TOMTOM_API_KEY = os.environ.get("TOMTOM_API_KEY", "")

INSTALLED_APPS = [
    "rest_framework",
    "planner",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.gzip.GZipMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
DATABASES = {}
USE_TZ = True
TIME_ZONE = "UTC"

# Run gunicorn with one worker and several threads so this cache is shared.
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "OPTIONS": {"MAX_ENTRIES": 20_000}}}

# The built React app is served from the site root by WhiteNoise.
FRONTEND_DIST = BASE_DIR.parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    WHITENOISE_ROOT = FRONTEND_DIST
    WHITENOISE_INDEX_FILE = True
    # Vite content-hashes everything in /assets/, so it can be cached forever.
    WHITENOISE_IMMUTABLE_FILE_TEST = lambda path, url: url.startswith("/assets/")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_THROTTLE_RATES": {"plan": "20/min"},
}
