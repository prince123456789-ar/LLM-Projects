from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.rate_limit import limiter
from app.core.security import api_key_hash
from app.models.embed_chat import EmbedConversation, EmbedMessage, EmbedMessageRole
from app.models.embed_key import EmbedKey
from app.models.lead import Lead, LeadChannel
from app.models.user import User
from app.schemas.embed_chat import EmbedChatMessageRequest, EmbedChatMessageResponse, EmbedPropertySuggestion
from app.services.agentic.team import agent_team_reply, meta_json
from app.services.assignment import assign_best_agent
from app.services.audit import audit_event

router = APIRouter(prefix="/embed/chat", tags=["embed-chat"])


def _auth_embed_key(db: Session, request: Request, key: str | None, x_embed_key: str | None) -> tuple[EmbedKey, User]:
    settings = get_settings()
    token = (x_embed_key or key or "").strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing embed key")

    token_h = api_key_hash(token, settings.SECRET_KEY)
    row = db.query(EmbedKey).filter(EmbedKey.token_hash == token_h, EmbedKey.revoked_at.is_(None)).first()
    if not row:
        raise HTTPException(status_code=401, detail="Invalid embed key")

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
    return row, user


def _get_or_create_conversation(db: Session, user: User, embed_key: EmbedKey, conversation_id: int | None) -> EmbedConversation:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if conversation_id:
        conv = db.query(EmbedConversation).filter(EmbedConversation.id == conversation_id, EmbedConversation.user_id == user.id).first()
        if conv:
            conv.last_seen_at = now
            db.commit()
            return conv

    conv = EmbedConversation(user_id=user.id, embed_key_id=embed_key.id, last_seen_at=now)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return conv


@router.post("/message", response_model=EmbedChatMessageResponse)
@limiter.limit("60/minute")
def chat_message(
    request: Request,
    payload: EmbedChatMessageRequest,
    db: Session = Depends(get_db),
    key: str | None = Query(default=None),
    x_embed_key: str | None = Header(default=None, alias="x-embed-key"),
):
    embed_key, user = _auth_embed_key(db, request, key=key, x_embed_key=x_embed_key)
    conv = _get_or_create_conversation(db, user, embed_key, payload.conversation_id)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    db.add(
        EmbedMessage(
            conversation_id=conv.id,
            role=EmbedMessageRole.user,
            content=payload.message,
            meta_json=meta_json(page_url=payload.page_url, referrer=payload.referrer),
            created_at=now,
        )
    )
    db.commit()

    result = agent_team_reply(db, payload.message)
    db.add(
        EmbedMessage(
            conversation_id=conv.id,
            role=EmbedMessageRole.assistant,
            content=result.reply,
            meta_json=meta_json(extracted=result.extracted),
            created_at=now,
        )
    )
    db.commit()

    # Create/append to a Lead record (best-effort).
    lead_id = None
    try:
        email = result.extracted.get("email")
        phone = result.extracted.get("phone")
        lead = None
        if email or phone:
            q = db.query(Lead)
            if email:
                q = q.filter(Lead.email == email)
            if phone:
                q = q.filter(Lead.phone == phone)
            lead = q.order_by(Lead.created_at.desc()).first()

        if not lead:
            lead = Lead(
                full_name="Website Visitor",
                email=result.extracted.get("email"),
                phone=result.extracted.get("phone"),
                channel=LeadChannel.website_chat,
                raw_message=f"[Chat] {payload.message}",
                property_type=result.extracted.get("property_type"),
                location=result.extracted.get("location"),
                budget=result.extracted.get("budget"),
                timeline=result.extracted.get("timeline"),
                score=0.0,
            )
            db.add(lead)
            db.flush()
            lead.assigned_agent_id = assign_best_agent(db, lead)
            db.commit()
            db.refresh(lead)
            audit_event(db, "embed_chat_lead_create", "lead", user_id=user.id, details=f"lead_id={lead.id}")
        else:
            lead.raw_message = (lead.raw_message + "\n---\n" + f"[Chat] {payload.message}").strip()
            db.commit()
        lead_id = lead.id
    except Exception:
        # Don't break chat if lead creation fails.
        pass

    recs = [EmbedPropertySuggestion(**r) for r in result.recommendations]
    return EmbedChatMessageResponse(conversation_id=conv.id, reply=result.reply, lead_id=lead_id, recommendations=recs)

