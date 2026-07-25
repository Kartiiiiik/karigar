#!/usr/bin/env sh
set -e

# The web container (and only it) runs migrations and collects static on boot.
# Worker/beat containers set RUN_MIGRATIONS=0 to skip this.
if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  echo "Applying database migrations..."
  python manage.py migrate --noinput

  echo "Collecting static files..."
  python manage.py collectstatic --noinput

  # Bootstrap the platform superuser from env (idempotent; no-op if it exists
  # or if the vars are unset).
  python manage.py ensure_superuser
fi

exec "$@"
