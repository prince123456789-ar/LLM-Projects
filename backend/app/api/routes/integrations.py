from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.core.security import verify_webhook_signature
from app.models.integration import CalendarIntegration, ChannelIntegration
from app.models.lead import Lead, LeadChannel
from app.models.user import User, UserRole
from app.schemas.integration import (
    ChannelIntegrationCreate,
    ChannelIntegrationResponse,
    MetaSendMessageRequest,
    WebhookLeadIngest,
)
from app.services.assignment import assign_best_agent
from app.services.audit import audit_event
from app.services.messaging import dispatch_message
from app.services.meta import parse_integration_metadata, parse_meta_messages, verify_meta_signature
from app.services.nlp import extract_entities, score_lead

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.post("/channels", response_model=ChannelIntegrationResponse)
def create_or_update_channel_integration(
    payload: ChannelIntegrationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin, UserRole.manager)),
):
    item = db.query(ChannelIntegration).filter(ChannelIntegration.channel == payload.channel).first()
    if not item:
        item = ChannelIntegration(**payload.model_dump())
        db.add(item)
    else:
        for k, v in payload.model_dump().items():
            setattr(item, k, v)

    db.commit()
    db.refresh(item)
    audit_event(db, "integration_upsert", "channel_integration", user_id=current_user.id)
    return item


@router.get("/channels", response_model=list[ChannelIntegrationResponse])
def list_channel_integrations(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.admin, UserRole.manager)),
):
    return db.query(ChannelIntegration).all()


@router.post("/calendar/{user_id}")
def connect_calendar(
    user_id: int,
    refresh_token_ref: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role == UserRole.agent and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Agents can connect only their own calendar")
    if current_user.role not in {UserRole.admin, UserRole.manager, UserRole.agent}:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    item = db.query(CalendarIntegration).filter(CalendarIntegration.user_id == user_id).first()
    if not item:
        item = CalendarIntegration(user_id=user_id, refresh_token_ref=refresh_token_ref, is_active=True)
        db.add(item)
    else:
        item.refresh_token_ref = refresh_token_ref
        item.is_active = True

    db.commit()
    audit_event(db, "calendar_connect", "calendar_integration", user_id=current_user.id, details=f"target_user={user_id}")
    return {"status": "connected", "user_id": user_id}


@router.get("/meta/webhook/{channel}")
def verify_meta_webhook(
    channel: LeadChannel,
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
    db: Session = Depends(get_db),
):
    integration = db.query(ChannelIntegration).filter(ChannelIntegration.channel == channel).first()
    metadata = parse_integration_metadata(integration.metadata_json if integration else None)
    settings = get_settings()

    verify_token = metadata.get("meta_verify_token") or settings.META_VERIFY_TOKEN
    if hub_mode == "subscribe" and verify_token and hub_verify_token == verify_token:
        return PlainTextResponse(content=hub_challenge)
    raise HTTPException(status_code=403, detail="Meta webhook verification failed")


@router.post("/meta/webhook/{channel}")
async def ingest_meta_webhook(
    channel: LeadChannel,
    request: Request,
    x_hub_signature_256: str | None = Header(default=None, alias="x-hub-signature-256"),
    db: Session = Depends(get_db),
):
    integration = db.query(ChannelIntegration).filter(ChannelIntegration.channel == channel).first()
    if not integration:
        raise HTTPException(status_code=404, detail="Channel integration not configured")

    raw_body = await request.body()
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    metadata = parse_integration_metadata(integration.metadata_json)
    settings = get_settings()
    app_secret = metadata.get("meta_app_secret") or settings.META_APP_SECRET
    if app_secret and not verify_meta_signature(app_secret, raw_body, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid Meta signature")

    parsed_messages = parse_meta_messages(channel.value, payload)
    created_ids: list[int] = []
    for msg in parsed_messages:
        extraction = extract_entities((msg.get("message") or "").strip())
        lead = Lead(
            full_name=(msg.get("full_name") or "Meta Lead")[:120],
            email=None,
            phone=msg.get("phone"),
            channel=channel,
            raw_message=(msg.get("message") or "")[:4000],
            score=score_lead(extraction.intent, extraction.budget, extraction.timeline),
            property_type=extraction.property_type,
            location=extraction.location,
            budget=extraction.budget,
            timeline=extraction.timeline,
        )
        db.add(lead)
        db.flush()
        lead.assigned_agent_id = assign_best_agent(db, lead)
        created_ids.append(lead.id)

    db.commit()
    audit_event(db, "meta_webhook_ingest", "lead", details=f"channel={channel.value};count={len(created_ids)}")
    return {"status": "accepted", "count": len(created_ids), "lead_ids": created_ids}


@router.post("/meta/send-test")
def send_meta_test_message(
    payload: MetaSendMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin, UserRole.manager)),
):
    result = dispatch_message(
        db,
        payload.channel,
        {
            "to": payload.recipient_id,
            "content": payload.content,
        },
    )
    audit_event(db, "meta_send_test", "integration", user_id=current_user.id, details=f"channel={payload.channel.value}")
    return result


@router.post("/webhooks/{channel}")
async def ingest_webhook_lead(
    channel: LeadChannel,
    request: Request,
    payload: WebhookLeadIngest,
    x_webhook_token: str | None = Header(default=None),
    x_webhook_timestamp: str | None = Header(default=None),
    x_webhook_signature: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    settings = get_settings()

    if settings.WEBHOOK_SHARED_SECRET:
        if x_webhook_token != settings.WEBHOOK_SHARED_SECRET:
            raise HTTPException(status_code=401, detail="Invalid webhook token")

        raw_body = await request.body()
        if not x_webhook_timestamp or not x_webhook_signature:
            raise HTTPException(status_code=401, detail="Missing webhook signature")

        if not verify_webhook_signature(
            settings.WEBHOOK_SHARED_SECRET,
            x_webhook_timestamp,
            raw_body,
            x_webhook_signature,
            settings.WEBHOOK_MAX_SKEW_SECONDS,
        ):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")

    extraction = extract_entities(payload.message)
    lead = Lead(
        full_name=payload.full_name,
        email=payload.email,
        phone=payload.phone,
        channel=channel,
        raw_message=payload.message,
        score=score_lead(extraction.intent, extraction.budget, extraction.timeline),
        property_type=extraction.property_type,
        location=extraction.location,
        budget=extraction.budget,
        timeline=extraction.timeline,
    )
    db.add(lead)
    db.flush()
    lead.assigned_agent_id = assign_best_agent(db, lead)
    db.commit()

    audit_event(db, "webhook_ingest", "lead", details=f"channel={channel.value};lead_id={lead.id}")
    return {"status": "accepted", "lead_id": lead.id}
