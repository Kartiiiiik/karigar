"""Expose the Celery app so shared_task decorators find it on Django startup.

Guarded so the project still boots if Celery isn't installed in a given
environment (e.g. a minimal CI job that only runs migrations checks).
"""
try:
    from .celery import app as celery_app

    __all__ = ("celery_app",)
except Exception:  # pragma: no cover - celery optional at import time
    __all__ = ()
