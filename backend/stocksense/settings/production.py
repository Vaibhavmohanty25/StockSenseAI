from django.core.exceptions import ImproperlyConfigured

from .base import *

DEBUG = False
if len(SECRET_KEY) < 50 or SECRET_KEY.startswith("replace-") or not ALLOWED_HOSTS:
    raise ImproperlyConfigured("Production requires a strong secret and allowed hosts.")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
SECURE_HSTS_SECONDS = env.int("DJANGO_SECURE_HSTS_SECONDS", default=31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
