# htr_seg_select

## Deployment (Production)

To use production-grade settings, set the environment variable:

```sh
export DJANGO_SETTINGS_MODULE="htr_seg_select.production"
```

### Required environment variables

- `DJANGO_SECRET_KEY`: Secure and random, required
- `DJANGO_ALLOWED_HOSTS`: Comma-separated domains/IPs (e.g., "mydomain.com,www.mydomain.com"), required
- `DJANGO_DB_NAME`: Postgres database name
- `DJANGO_DB_USER`: Postgres user
- `DJANGO_DB_PASSWORD`: Postgres password
- `DJANGO_DB_HOST`: Postgres hostname
- `DJANGO_DB_PORT`: Postgres port
- `DJANGO_STATIC_ROOT`: Absolute path for collected static files (e.g. `/srv/app/staticfiles`)
- `DJANGO_MEDIA_ROOT`: Absolute path for uploaded media (e.g. `/srv/app/media`)

### Static and media files for nginx

Collect static files for nginx to serve directly:

```sh
python manage.py collectstatic --settings=htr_seg_select.production
```

Nginx should be configured to serve files from `$DJANGO_STATIC_ROOT` and `$DJANGO_MEDIA_ROOT`.

### Running with gunicorn

Start gunicorn in production mode:

```sh
gunicorn htr_seg_select.wsgi:application --env DJANGO_SETTINGS_MODULE=htr_seg_select.production
```

## Local development

You can run Django locally with:

```sh
python manage.py runserver
```
This uses `settings.py`, which defaults to development behavior.