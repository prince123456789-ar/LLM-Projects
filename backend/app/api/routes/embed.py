from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.security import api_key_hash
from app.models.embed_key import EmbedKey
from app.models.lead import Lead, LeadChannel
from app.models.user import User
from app.schemas.embed import EmbedKeyResponse, EmbedLeadCreate
from app.services.assignment import assign_best_agent
from app.services.audit import audit_event
from app.services.crypto import fernet_from_secret
from app.services.nlp import extract_entities, score_lead

router = APIRouter(prefix="/embed", tags=["embed"])


def _masked(prefix: str) -> str:
    # Prefix is safe to show; keep it short.
    p = (prefix or "")[:12]
    return f"{p}...{p[-4:]}" if len(p) >= 8 else f"{p}..."


def _make_install(key_plain: str, request: Request) -> tuple[str, str]:
    # Serve embed.js from the same origin as the backend.
    origin = str(request.base_url).rstrip("/")
    install_script_url = f"{origin}/embed.js?key={key_plain}"
    snippet = f'<script src="{install_script_url}" async></script>'
    return install_script_url, snippet


def _ensure_primary_key(db: Session, user: User, request: Request) -> tuple[EmbedKey, str]:
    settings = get_settings()
    row = (
        db.query(EmbedKey)
        .filter(EmbedKey.user_id == user.id, EmbedKey.revoked_at.is_(None))
        .order_by(EmbedKey.created_at.desc())
        .first()
    )
    f = fernet_from_secret(settings.SECRET_KEY)

    if row:
        try:
            plain = f.decrypt(row.token_enc.encode("utf-8")).decode("utf-8")
            # If we changed the prefix format, rotate old keys automatically.
            if not plain.startswith(settings.EMBED_KEY_PREFIX):
                row.revoked_at = datetime.now(timezone.utc).replace(tzinfo=None)
                db.commit()
                row = None
            else:
                return row, plain
        except Exception:
            # If decrypt fails (key rotated), rotate automatically.
            row.revoked_at = datetime.now(timezone.utc).replace(tzinfo=None)
            db.commit()

    # Create new (opaque, unguessable).
    base = api_key_hash(f"{user.id}:{datetime.utcnow().timestamp()}", settings.SECRET_KEY)[:32]
    salt = api_key_hash(base + api_key_hash(base, settings.SECRET_KEY), settings.SECRET_KEY)[:16]
    plain = f"{settings.EMBED_KEY_PREFIX}{base}{salt}"
    prefix = plain[:12]
    row = EmbedKey(
        user_id=user.id,
        prefix=prefix,
        token_hash=api_key_hash(plain, settings.SECRET_KEY),
        token_enc=f.encrypt(plain.encode("utf-8")).decode("utf-8"),
        allowed_origins=None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    audit_event(db, "embed_key_create", "embed_key", user_id=user.id, details=f"embed_key_id={row.id}")
    return row, plain


def _get_current_user_for_embed_keys():
    # Local import avoids circular imports.
    from app.core.deps import require_roles
    from app.models.user import UserRole

    return require_roles(UserRole.admin, UserRole.manager)


@router.get("/keys/primary", response_model=EmbedKeyResponse)
def primary_embed_key(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(_get_current_user_for_embed_keys()),
):
    row, plain = _ensure_primary_key(db, current_user, request)
    install_url, snippet = _make_install(plain, request)
    return EmbedKeyResponse(id=row.id, masked_key=_masked(row.prefix), install_script_url=install_url, install_snippet=snippet)


@router.post("/leads")
def ingest_embed_lead(
    payload: EmbedLeadCreate,
    request: Request,
    db: Session = Depends(get_db),
    x_embed_key: str | None = Header(default=None, alias="x-embed-key"),
    key: str | None = Query(default=None),
):
    settings = get_settings()
    token = (x_embed_key or key or "").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing embed key")

    token_h = api_key_hash(token, settings.SECRET_KEY)
    row = db.query(EmbedKey).filter(EmbedKey.token_hash == token_h, EmbedKey.revoked_at.is_(None)).first()
    if not row:
        raise HTTPException(status_code=401, detail="Invalid embed key")

    # Optional origin allowlist.
    origin = (request.headers.get("origin") or "").strip()
    if row.allowed_origins:
        allowed = [o.strip() for o in row.allowed_origins.split(",") if o.strip()]
        if origin and origin not in allowed:
            raise HTTPException(status_code=403, detail="Origin not allowed")

    user = db.query(User).filter(User.id == int(row.user_id)).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid embed key")

    row.last_used_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()

    raw = (payload.message or "").strip()
    if not raw:
        parts = []
        if payload.property_type:
            parts.append(f"Property type: {payload.property_type}")
        if payload.location:
            parts.append(f"Location: {payload.location}")
        if payload.budget is not None:
            parts.append(f"Budget: {payload.budget}")
        if payload.timeline:
            parts.append(f"Timeline: {payload.timeline}")
        raw = " | ".join(parts) if parts else "New lead"

    # Add lightweight provenance for support/debugging.
    if payload.page_url:
        raw = f"[Embed] {raw}\nPage: {payload.page_url}"
    if payload.referrer:
        raw = f"{raw}\nReferrer: {payload.referrer}"

    extraction = extract_entities(raw)
    score = score_lead(extraction.intent, extraction.budget, extraction.timeline)

    lead = Lead(
        full_name=payload.full_name,
        email=payload.email,
        phone=payload.phone,
        channel=LeadChannel.website_chat,
        raw_message=raw,
        score=score,
        property_type=payload.property_type or extraction.property_type,
        location=payload.location or extraction.location,
        budget=payload.budget or extraction.budget,
        timeline=payload.timeline or extraction.timeline,
    )
    db.add(lead)
    db.flush()
    lead.assigned_agent_id = assign_best_agent(db, lead)
    db.commit()
    db.refresh(lead)

    audit_event(db, "embed_lead_ingest", "lead", user_id=user.id, details=f"lead_id={lead.id}")
    return {"status": "ok", "lead_id": lead.id}
