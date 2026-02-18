from .base import *

# Production overrides

DEBUG = False

SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]

ALLOWED_HOSTS = os.environ["DJANGO_ALLOWED_HOSTS"].split(",")

# Security settings for nginx TLS termination (proxy, HSTS, secure cookies)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Static/media config for collectstatic + nginx serve
STATIC_ROOT = os.environ.get("DJANGO_STATIC_ROOT", str(BASE_DIR / "staticfiles"))
MEDIA_ROOT = os.environ.get("DJANGO_MEDIA_ROOT", str(BASE_DIR / "media"))

# Example mandatory environment variables for production:
#   DJANGO_SECRET_KEY      -- securely generated, mandatory
#   DJANGO_ALLOWED_HOSTS   -- comma-separated, mandatory (e.g. "mydomain.com,www.mydomain.com")
#   DJANGO_DB_NAME         -- Postgres DB name
#   DJANGO_DB_USER         -- Postgres username
#   DJANGO_DB_PASSWORD     -- Postgres password
#   DJANGO_DB_HOST         -- Postgres hostname
#   DJANGO_DB_PORT         -- Postgres port
#   DJANGO_STATIC_ROOT     -- absolute path for static file collection
#   DJANGO_MEDIA_ROOT      -- absolute path for media files