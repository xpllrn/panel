"""
URLconf for the API-only service (`config.settings_api`).

Mounted by the `api` container in docker-compose. Exposes ONLY:
- the JSON `/api/v1/` surface from `accounts.api_urls`
- the OpenAPI schema + Swagger docs
- a `/health/` probe for load balancers

Deliberately omits:
- every HTML route (admin_portal, member_portal, setup wizard, login)
- the Django admin (`/admin/`)
- the `AutoStaffLoginMiddleware` (turned off in `config/settings_api.py`)

This separation is a security boundary: an HTML-targeted bug or auto-login
shortcut cannot reach this service.
"""

from django.http import JsonResponse
from django.urls import include, path

from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView


def health_check(request):
    """Health check endpoint for uptime monitoring and load balancers."""
    from django.db import connection

    try:
        connection.ensure_connection()
        return JsonResponse({"status": "ok", "service": "api", "database": "connected"})
    except Exception:
        return JsonResponse({"status": "error", "service": "api", "database": "disconnected"}, status=503)


def api_root(request):
    """Friendly root for the API service so / does not 404."""
    return JsonResponse(
        {
            "service": "panel-erp-api",
            "version": "1.0.0",
            "endpoints": {
                "v1": "/api/v1/",
                "schema": "/api/v1/schema/",
                "docs": "/api/v1/docs/",
                "health": "/health/",
            },
        }
    )


urlpatterns = [
    path("", api_root, name="api_root"),
    path("health/", health_check, name="health_check"),
    path("api/v1/", include("accounts.api_urls")),
    path("api/v1/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/v1/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
]
