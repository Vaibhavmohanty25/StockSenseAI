import os

# Ephemeral test signing material, never a deployable application secret.
os.environ.setdefault("DJANGO_SECRET_KEY", "test-only-not-for-deployment")
os.environ.setdefault("POSTGRES_PASSWORD", "")

from .base import *  # noqa: E402

DEBUG = False
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]
DATABASES["default"]["CONN_MAX_AGE"] = 0
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
