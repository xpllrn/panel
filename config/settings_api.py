"""
Django settings for the API-only service.

Imports everything from `config.settings` and overrides what must be different
for the standalone REST API process:

1. `ROOT_URLCONF` points to `config.urls_api` (only `/api/v1/...`, schema, docs,
   health). No HTML route, no Django admin.
2. `AutoStaffLoginMiddleware` is REMOVED. The HTML panel auto-attaches the first
   staff user to anonymous sessions when `WEB_LOGIN_DISABLED=True`; that magic
   must never run on the API surface, where all authentication is JWT/OTP-based.
3. Panel-only template context processors are dropped — the API never renders
   templates, so loading `admin_portal.context_processors.*` would just import
   admin_portal at boot for no reason.

Run with:

    DJANGO_SETTINGS_MODULE=config.settings_api python manage.py runserver 0.0.0.0:8001

or in production:

    DJANGO_SETTINGS_MODULE=config.settings_api gunicorn --bind 0.0.0.0:8001 config.wsgi:application
"""

from config.settings import *  # noqa: F401, F403
from config.settings import MIDDLEWARE, TEMPLATES

ROOT_URLCONF = "config.urls_api"

# Strip the staff-auto-login middleware. Belt-and-braces: `urls_api` does not
# expose any non-/api/ HTML route, but removing the middleware entirely makes
# the security boundary independent of URL routing.
MIDDLEWARE = [m for m in MIDDLEWARE if m != "accounts.middleware.AutoStaffLoginMiddleware"]

# Drop panel-only template context processors. The API does not render any
# Django template; keeping these would force `admin_portal` imports at boot
# and could leak panel-specific state.
_PANEL_ONLY_CTX = {
    "admin_portal.context_processors.portal_fy",
    "admin_portal.context_processors.web_auth_context",
}
TEMPLATES = [dict(_t) for _t in TEMPLATES]
for _t in TEMPLATES:
    _opts = dict(_t.get("OPTIONS") or {})
    _opts["context_processors"] = [
        cp for cp in _opts.get("context_processors", []) if cp not in _PANEL_ONLY_CTX
    ]
    _t["OPTIONS"] = _opts
