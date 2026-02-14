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
from app.models import appointment, audit, billing, embed_chat, embed_key, integration, lead, property, report, user  # noqa: F401

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
    # Website chat widget: a tiny embedded chat UI that talks to our server-side agent team.
    js = f"""(function() {{
  'use strict';
  function findScriptSrc() {{
    try {{
      if (document.currentScript && document.currentScript.src) return document.currentScript.src;
    }} catch (e) {{}}
    try {{
      var scripts = document.querySelectorAll('script[src]');
      for (var i = scripts.length - 1; i >= 0; i--) {{
        var s = scripts[i].getAttribute('src') || '';
        if (s.indexOf('/embed.js') !== -1 && s.indexOf('key=') !== -1) return scripts[i].src || s;
      }}
    }} catch (e) {{}}
    return '';
  }}

  var src = findScriptSrc();
  var u = null;
  try {{ u = new URL(src); }} catch (e) {{}}
  var backendOrigin = u ? u.origin : '';
  var key = '';
  try {{
    if (u && u.searchParams) key = u.searchParams.get('key') || '';
  }} catch (e) {{}}
  if (!key || !backendOrigin) return;

  function cssText() {{
    return [
      '.reai-fab{{position:fixed;right:18px;bottom:18px;z-index:2147483647;background:linear-gradient(135deg,#3b82f6,#2dd4bf);color:#081018;border:0;border-radius:999px;padding:12px 14px;font:800 14px/1.1 ui-sans-serif,system-ui;box-shadow:0 18px 55px rgba(59,130,246,.22);cursor:pointer}}',
      '.reai-panel{{position:fixed;right:18px;bottom:78px;z-index:2147483647;width:min(420px,92vw);height:min(560px,78vh);display:none;flex-direction:column;border-radius:22px;overflow:hidden;border:1px solid rgba(255,255,255,.12);background:rgba(8,10,16,.88);backdrop-filter: blur(14px);box-shadow:0 24px 70px rgba(0,0,0,.55)}}',
      '.reai-head{{padding:14px 14px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid rgba(255,255,255,.10);background:rgba(255,255,255,.03)}}',
      '.reai-title{{display:flex;flex-direction:column;gap:2px}}',
      '.reai-title b{{font:800 14px/1.1 ui-sans-serif,system-ui;color:#eaf0ff;letter-spacing:.2px}}',
      '.reai-title span{{font:600 11px/1 ui-sans-serif,system-ui;color:rgba(234,240,255,.65)}}',
      '.reai-x{{border:1px solid rgba(255,255,255,.14);background:rgba(255,255,255,.05);color:#eaf0ff;border-radius:999px;padding:7px 10px;font:700 12px/1 ui-sans-serif,system-ui;cursor:pointer}}',
      '.reai-body{{flex:1;overflow:auto;padding:14px;display:flex;flex-direction:column;gap:10px}}',
      '.reai-msg{{max-width:88%;padding:10px 12px;border-radius:16px;border:1px solid rgba(255,255,255,.10);font:600 13px/1.35 ui-sans-serif,system-ui;white-space:pre-wrap;overflow-wrap:anywhere}}',
      '.reai-u{{align-self:flex-end;background:rgba(59,130,246,.12);border-color:rgba(59,130,246,.22);color:#dbeafe}}',
      '.reai-a{{align-self:flex-start;background:rgba(45,212,191,.10);border-color:rgba(45,212,191,.20);color:#ccfbf1}}',
      '.reai-foot{{padding:12px;border-top:1px solid rgba(255,255,255,.10);display:flex;gap:10px}}',
      '.reai-in{{flex:1;padding:10px 12px;border-radius:16px;border:1px solid rgba(255,255,255,.12);background:rgba(0,0,0,.20);color:#eaf0ff;outline:none;font:600 13px/1.2 ui-sans-serif,system-ui}}',
      '.reai-send{{padding:10px 12px;border-radius:16px;border:0;background:linear-gradient(135deg,#3b82f6,#2dd4bf);color:#081018;font:900 13px/1 ui-sans-serif,system-ui;cursor:pointer}}'
    ].join('');
  }}

  function el(tag, attrs) {{
    var n = document.createElement(tag);
    if (attrs) {{
      Object.keys(attrs).forEach(function(k) {{
        if (k === 'text') n.textContent = attrs[k];
        else n.setAttribute(k, attrs[k]);
      }});
    }}
    return n;
  }}

  function appendMsg(box, cls, text) {{
    var m = el('div', {{ class: 'reai-msg ' + cls }});
    m.textContent = text;
    box.appendChild(m);
    box.scrollTop = box.scrollHeight;
  }}

  var style = el('style'); style.textContent = cssText(); document.head.appendChild(style);
  var fab = el('button', {{ class:'reai-fab', type:'button', text:'Chat' }});
  var panel = el('div', {{ class:'reai-panel' }});
  var head = el('div', {{ class:'reai-head' }});
  var title = el('div', {{ class:'reai-title' }});
  title.appendChild(el('b', {{ text:'RealEstateAI Agent Team' }}));
  title.appendChild(el('span', {{ text:'Lead capture + qualification in real time' }}));
  var close = el('button', {{ class:'reai-x', type:'button', text:'Close' }});
  head.appendChild(title); head.appendChild(close);
  var body = el('div', {{ class:'reai-body' }});
  var foot = el('div', {{ class:'reai-foot' }});
  var input = el('input', {{ class:'reai-in', placeholder:'Type your message...' }});
  var send = el('button', {{ class:'reai-send', type:'button', text:'Send' }});
  foot.appendChild(input); foot.appendChild(send);
  panel.appendChild(head); panel.appendChild(body); panel.appendChild(foot);

  function open() {{ panel.style.display='flex'; input.focus(); }}
  function hide() {{ panel.style.display='none'; }}
  fab.addEventListener('click', open);
  close.addEventListener('click', hide);

  var convKey = 'reai_conv_' + key.slice(0, 16);
  function getConv() {{ try {{ return localStorage.getItem(convKey) || ''; }} catch(e) {{ return ''; }} }}
  function setConv(v) {{ try {{ localStorage.setItem(convKey, v); }} catch(e) {{}} }}

  var booted = false;
  function boot() {{
    if (booted) return;
    booted = true;
    appendMsg(body, 'reai-a', 'Hi. Tell me the location, budget, and property type you are looking for.');
  }}
  fab.addEventListener('click', boot);

  function sendMsg() {{
    var t = (input.value || '').trim();
    if (!t) return;
    input.value = '';
    appendMsg(body, 'reai-u', t);
    var payload = {{
      conversation_id: getConv() || null,
      message: t,
      page_url: (location && location.href) ? String(location.href) : null,
      referrer: (document && document.referrer) ? String(document.referrer) : null
    }};
    fetch(backendOrigin + '/api/v1/embed/chat/message?key=' + encodeURIComponent(key), {{
      method:'POST',
      headers: {{ 'Content-Type':'application/json' }},
      body: JSON.stringify(payload)
    }}).then(function(r) {{
      return r.json().catch(function(){{return {{}};}}).then(function(j){{ return {{ ok:r.ok, json:j }}; }});
    }}).then(function(res) {{
      if (!res.ok) throw new Error((res.json && res.json.detail) ? res.json.detail : 'Failed');
      if (res.json && res.json.conversation_id) setConv(String(res.json.conversation_id));
      appendMsg(body, 'reai-a', String(res.json.reply || 'Okay.'));
      if (res.json && res.json.recommendations && res.json.recommendations.length) {{
        var list = res.json.recommendations.map(function(p) {{
          return '- ' + p.title + ' | ' + p.location + ' | $' + p.price;
        }}).join('\\n');
        appendMsg(body, 'reai-a', 'Suggested listings:\\n' + list);
      }}
    }}).catch(function(err) {{
      appendMsg(body, 'reai-a', (err && err.message) ? err.message : 'Request failed.');
    }});
  }}

  send.addEventListener('click', sendMsg);
  input.addEventListener('keydown', function(e) {{ if (e.key === 'Enter') sendMsg(); }});

  function mount() {{
    try {{
      if (!document.body) return;
      document.body.appendChild(fab);
      document.body.appendChild(panel);
    }} catch (e) {{}}
  }}

  if (document.readyState === 'loading') {{
    document.addEventListener('DOMContentLoaded', mount, {{ once:true }});
  }} else {{
    mount();
  }}
}})();"""
    return Response(
        content=js,
        media_type="application/javascript; charset=utf-8",
        headers={"Cache-Control": "no-store"},
    )


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
