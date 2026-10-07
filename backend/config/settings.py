import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-insecure-key-change-me")
DEBUG = os.environ.get("DEBUG", "true").lower() == "true"
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = ["corsheaders", "trips"]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# No database needed: the API is stateless.
DATABASES = {}

# CORS: set CORS_ALLOWED_ORIGINS="https://your-app.vercel.app,http://localhost:5173"
_origins = os.environ.get("CORS_ALLOWED_ORIGINS", "")
if _origins:
    CORS_ALLOWED_ORIGINS = [o.strip() for o in _origins.split(",") if o.strip()]
else:
    CORS_ALLOW_ALL_ORIGINS = True

USE_TZ = False
TIME_ZONE = "UTC"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
