# syntax=docker/dockerfile:1
# ===========================================================================
# Multi-stage production image for the Django backend.
#   Stage 1 (builder): compile wheels into a virtualenv.
#   Stage 2 (runtime): slim image with only runtime libs + the venv.
# ===========================================================================

# --------------------------- Stage 1: builder ------------------------------
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Build-time deps for psycopg and WeasyPrint's native extensions.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# --------------------------- Stage 2: runtime ------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=config.settings.prod

# Runtime libraries:
#   postgresql-client   -> pg_dump / pg_restore for backups (Debian's client is
#                          >= the Postgres 16 server, which pg_dump supports)
#   libpango/cairo/…    -> WeasyPrint PDF rendering
#   fonts               -> legible PDFs
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-client \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libffi8 \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv

# Non-root user.
RUN useradd --create-home --uid 1000 appuser
WORKDIR /app
COPY --chown=appuser:appuser . /app
# Create the media/static mount points owned by appuser so the named volumes
# mounted here initialise with writable (non-root) ownership.
RUN chmod +x /app/entrypoint.sh \
    && mkdir -p /app/staticfiles /app/media /app/backups \
    && chown -R appuser:appuser /app/staticfiles /app/media /app/backups
USER appuser

EXPOSE 8000
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]
