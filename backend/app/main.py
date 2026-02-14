from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi import _rate_limit_exceeded_handler
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.api import api_router
from app.core.config import get_settings
from app.core.database import Base, engine
from app.core.middleware import RequestIDMiddleware, SecurityHeadersMiddleware
from app.core.rate_limit import limiter
from app.models import appointment, audit, billing, integration, lead, property, report, user  # noqa: F401

settings = get_settings()

app = FastAPI(
    title=settings.PROJECT_NAME,
    docs_url="/docs" if settings.ENABLE_API_DOCS else None,
    redoc_url="/redoc" if settings.ENABLE_API_DOCS else None,
    openapi_url="/openapi.json" if settings.ENABLE_API_DOCS else None,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "x-device-id", "x-request-id", "x-webhook-timestamp", "x-webhook-signature"],
)


@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)


@app.get("/health")
@limiter.limit("60/minute")
def health(request: Request):
    return {"status": "ok"}


_web_dir = Path(__file__).resolve().parent / "web"
_site_dir = _web_dir / "site"
app.mount("/static", StaticFiles(directory=str(_web_dir / "static")), name="static")


def _page(name: str) -> FileResponse:
    return FileResponse(str(_site_dir / name))


@app.get("/", include_in_schema=False)
def ui_home():
    return _page("index.html")

@app.get("/api", include_in_schema=False)
def api_root():
    return {
        "name": settings.PROJECT_NAME,
        "version": "v1",
        "base": settings.API_V1_STR,
        "health": "/health",
    }


@app.get(settings.API_V1_STR, include_in_schema=False)
def api_v1_root():
    return {
        "base": settings.API_V1_STR,
        "endpoints": [
            "/auth/login",
            "/auth/register",
            "/auth/refresh",
            "/leads",
            "/analytics/dashboard",
            "/analytics/timeseries",
        ],
    }


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    # Avoid showing JSON {"detail":"Not Found"} in browsers for UI routes.
    if exc.status_code == 404:
        accept = (request.headers.get("accept") or "").lower()
        if "text/html" in accept:
            return _page("404.html")
        return JSONResponse(
            status_code=404,
            content={"detail": "Not Found", "path": str(request.url.path)},
        )
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.get("/pricing", include_in_schema=False)
def ui_pricing():
    return _page("pricing.html")


@app.get("/privacy", include_in_schema=False)
def ui_privacy():
    return _page("privacy.html")


@app.get("/terms", include_in_schema=False)
def ui_terms():
    return _page("terms.html")


@app.get("/app/login", include_in_schema=False)
def ui_login():
    return _page("app-login.html")

@app.get("/app/register", include_in_schema=False)
def ui_register():
    return _page("app-register.html")

@app.get("/app/forgot-password", include_in_schema=False)
def ui_forgot_password():
    return _page("app-forgot-password.html")


@app.get("/app/reset-password", include_in_schema=False)
def ui_reset_password():
    return _page("app-reset-password.html")


@app.get("/app/dashboard", include_in_schema=False)
def ui_dashboard():
    return _page("app-dashboard.html")


@app.get("/app/leads", include_in_schema=False)
def ui_leads():
    return _page("app-leads.html")


@app.get("/app/integrations", include_in_schema=False)
def ui_integrations():
    return _page("app-integrations.html")


@app.get("/app/appointments", include_in_schema=False)
def ui_appointments():
    return _page("app-appointments.html")


@app.get("/app/billing", include_in_schema=False)
def ui_billing():
    return _page("app-billing.html")

@app.get("/app/settings", include_in_schema=False)
def ui_settings():
    return _page("app-settings.html")


@app.get("/app/audit", include_in_schema=False)
def ui_audit():
    return _page("app-audit.html")


app.include_router(api_router, prefix=settings.API_V1_STR)
