"""Root URL configuration. The whole API lives under /api/v1/ via Ninja."""
from django.conf import settings
from django.contrib import admin
from django.urls import path, re_path
from django.views.static import serve

from .api import api

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", api.urls),
]

# Serve user-uploaded media from the local filesystem in ALL modes (not just
# DEBUG). While USE_S3 is off, photos live on disk under MEDIA_ROOT; nginx
# proxies /media/ to this service. The django.conf.urls.static.static() helper
# is a no-op when DEBUG=False, so wire the route explicitly. Fine for this
# internal, low-traffic shop tool; switch to S3 (USE_S3=True) to offload it.
urlpatterns += [
    re_path(
        r"^media/(?P<path>.*)$",
        serve,
        {"document_root": settings.MEDIA_ROOT},
    ),
]
