"""The single Ninja API instance, mounted at /api/v1/.

Registers every app router, a public health check, and exception handlers that
produce the consistent error envelope the frontend expects:

    {"error": {"code": <status>, "message": <str>, "detail": <any>}}
"""
import logging

from django.db import connection
from ninja import NinjaAPI
from ninja.errors import AuthenticationError, HttpError, ValidationError

from apps.accounts.api import router as accounts_router
from apps.backups.api import router as backups_router
from apps.bandaki.api import router as bandaki_router
from apps.common.auth import auth
from apps.ledger.api import router as ledger_router
from apps.reports.api import router as reports_router

logger = logging.getLogger("apps")

# Global default auth = JWT. Public endpoints opt out with auth=None.
api = NinjaAPI(title="Karigar API", version="1.0", auth=auth)

api.add_router("/auth", accounts_router)
api.add_router("", ledger_router)
api.add_router("", reports_router)
api.add_router("", backups_router)
api.add_router("", bandaki_router)


def _envelope(message, code, detail=None):
    return {"error": {"code": code, "message": message, "detail": detail}}


@api.exception_handler(ValidationError)
def on_validation_error(request, exc):
    return api.create_response(
        request, _envelope("Validation failed.", 422, exc.errors), status=422
    )


@api.exception_handler(AuthenticationError)
def on_auth_error(request, exc):
    return api.create_response(
        request, _envelope("Authentication credentials were not provided or are invalid.", 401), status=401
    )


@api.exception_handler(HttpError)
def on_http_error(request, exc):
    return api.create_response(
        request, _envelope(str(exc), exc.status_code), status=exc.status_code
    )


@api.exception_handler(Exception)
def on_unhandled(request, exc):
    logger.exception("Unhandled API exception")
    # Re-raise in DEBUG so Django's traceback page still helps locally.
    from django.conf import settings

    if settings.DEBUG:
        raise exc
    return api.create_response(request, _envelope("Internal server error.", 500), status=500)


@api.get("/health/", auth=None, tags=["system"])
def health(request):
    """Liveness + DB readiness. Public."""
    db_ok = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:  # pragma: no cover
        db_ok = False
    return {"status": "ok" if db_ok else "degraded", "database": db_ok}
