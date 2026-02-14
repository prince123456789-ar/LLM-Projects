from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse
from fastapi.responses import Response
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
from app.models import appointment, audit, billing, embed_key, integration, lead, property, report, user  # noqa: F401

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
    # Tokens are passed in headers, not cookies; keep credentials off so we can allow
    # broader cross-origin use for the website embed SDK.
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "x-device-id",
        "x-request-id",
        "x-webhook-timestamp",
        "x-webhook-signature",
        "x-api-key",
        "x-embed-key",
    ],
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

@app.get("/embed.js", include_in_schema=False)
def ui_embed_js(key: str = ""):
    # Minimal website widget: loads from a single script tag and POSTs to /api/v1/embed/leads.
    # Key is passed via query string to keep integration copy/paste simple.
    js = f"""(function() {{
  'use strict';
  var script = document.currentScript;
  var src = (script && script.src) ? script.src : '';
  var u = null;
  try {{ u = new URL(src); }} catch (e) {{}}
  var backendOrigin = u ? u.origin : '';
  var key = '';
  try {{
    if (u && u.searchParams) key = u.searchParams.get('key') || '';
  }} catch (e) {{}}
  if (!key) {{
    // No key: don't do anything.
    return;
  }}

  function cssText() {{
    return [
      '.reai-btn{{position:fixed;right:18px;bottom:18px;z-index:2147483647;background:linear-gradient(135deg,#55f2c2,#74a8ff);color:#041016;border:0;border-radius:999px;padding:12px 14px;font:600 14px/1.1 ui-sans-serif,system-ui;box-shadow:0 12px 30px rgba(0,0,0,.35);cursor:pointer}}',
      '.reai-modal{{position:fixed;inset:0;z-index:2147483647;display:none;align-items:center;justify-content:center;background:rgba(0,0,0,.55)}}',
      '.reai-card{{width:min(520px,92vw);border-radius:18px;padding:18px;background:rgba(10,14,22,.92);color:#eaf0ff;border:1px solid rgba(255,255,255,.12);box-shadow:0 18px 60px rgba(0,0,0,.45)}}',
      '.reai-row{{display:flex;gap:10px;flex-wrap:wrap}}',
      '.reai-card h3{{margin:0 0 10px 0;font:700 18px/1.2 ui-sans-serif,system-ui}}',
      '.reai-card p{{margin:0 0 14px 0;opacity:.8;font:400 13px/1.4 ui-sans-serif,system-ui}}',
      '.reai-in{{width:100%;padding:10px 12px;border-radius:12px;border:1px solid rgba(255,255,255,.14);background:rgba(255,255,255,.06);color:#eaf0ff;outline:none}}',
      '.reai-actions{{display:flex;gap:10px;align-items:center;justify-content:flex-end;margin-top:12px}}',
      '.reai-x{{background:transparent;border:1px solid rgba(255,255,255,.16);color:#eaf0ff;border-radius:12px;padding:9px 12px;cursor:pointer}}',
      '.reai-send{{background:linear-gradient(135deg,#55f2c2,#74a8ff);border:0;color:#041016;border-radius:12px;padding:9px 12px;cursor:pointer;font-weight:700}}',
      '.reai-msg{{margin-top:10px;opacity:.85;font:500 12px/1.2 ui-sans-serif,system-ui}}'
    ].join('');
  }}

  function el(tag, attrs) {{
    var n = document.createElement(tag);
    if (attrs) {{
      Object.keys(attrs).forEach(function(k) {{
        if (k === 'text') n.textContent = attrs[k];
        else if (k === 'html') n.innerHTML = attrs[k];
        else n.setAttribute(k, attrs[k]);
      }});
    }}
    return n;
  }}

  var style = el('style'); style.textContent = cssText(); document.head.appendChild(style);

  var btn = el('button', {{ class:'reai-btn', type:'button', text:'Contact Agent' }});
  var modal = el('div', {{ class:'reai-modal' }});
  var card = el('div', {{ class:'reai-card' }});
  modal.appendChild(card);

  card.appendChild(el('h3', {{ text:'Request a viewing' }}));
  card.appendChild(el('p', {{ text:'Leave your details and we will respond quickly.' }}));
  var name = el('input', {{ class:'reai-in', placeholder:'Full name', autocomplete:'name' }});
  var email = el('input', {{ class:'reai-in', placeholder:'Email (optional)', autocomplete:'email' }});
  var phone = el('input', {{ class:'reai-in', placeholder:'Phone (optional)', autocomplete:'tel' }});
  var msg = el('textarea', {{ class:'reai-in', placeholder:'Message (optional)', rows:'4' }});
  card.appendChild(name);
  card.appendChild(el('div', {{ style:'height:8px' }}));
  card.appendChild(email);
  card.appendChild(el('div', {{ style:'height:8px' }}));
  card.appendChild(phone);
  card.appendChild(el('div', {{ style:'height:8px' }}));
  card.appendChild(msg);
  var actions = el('div', {{ class:'reai-actions' }});
  var close = el('button', {{ class:'reai-x', type:'button', text:'Close' }});
  var send = el('button', {{ class:'reai-send', type:'button', text:'Send' }});
  actions.appendChild(close);
  actions.appendChild(send);
  card.appendChild(actions);
  var status = el('div', {{ class:'reai-msg', text:'' }});
  card.appendChild(status);

  function open() {{ modal.style.display='flex'; status.textContent=''; }}
  function hide() {{ modal.style.display='none'; }}

  btn.addEventListener('click', open);
  close.addEventListener('click', hide);
  modal.addEventListener('click', function(e) {{ if (e.target === modal) hide(); }});

  send.addEventListener('click', function() {{
    status.textContent = 'Sending...';
    var payload = {{
      full_name: (name.value || '').trim(),
      email: (email.value || '').trim() || null,
      phone: (phone.value || '').trim() || null,
      message: (msg.value || '').trim() || null,
      page_url: (location && location.href) ? String(location.href) : null,
      referrer: (document && document.referrer) ? String(document.referrer) : null
    }};
    if (!payload.full_name) {{
      status.textContent = 'Name is required.';
      return;
    }}
    fetch(backendOrigin + '/api/v1/embed/leads?key=' + encodeURIComponent(key), {{
      method: 'POST',
      headers: {{ 'Content-Type':'application/json' }},
      body: JSON.stringify(payload)
    }}).then(function(r) {{
      return r.json().catch(function() {{ return {{}}; }}).then(function(j) {{ return {{ ok:r.ok, json:j }}; }});
    }}).then(function(res) {{
      if (!res.ok) throw new Error((res.json && res.json.detail) ? res.json.detail : 'Failed');
      status.textContent = 'Sent. We will contact you shortly.';
      setTimeout(hide, 900);
    }}).catch(function(err) {{
      status.textContent = (err && err.message) ? err.message : 'Failed to send.';
    }});
  }});

  document.body.appendChild(btn);
  document.body.appendChild(modal);
}})();"""
    return Response(content=js, media_type="application/javascript; charset=utf-8")


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

@app.get("/app/admin", include_in_schema=False)
def ui_admin():
    return _page("app-admin.html")


app.include_router(api_router, prefix=settings.API_V1_STR)
