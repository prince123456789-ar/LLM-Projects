from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.models.lead import Lead, LeadStatus
from app.models.property import Property
from app.models.user import User, UserRole
from app.schemas.lead import LeadCreate, LeadResponse, LeadUpdate
from app.services.assignment import assign_best_agent
from app.services.audit import audit_event
from app.services.nlp import extract_entities, score_lead
from app.workers.tasks import send_followup_message

router = APIRouter(prefix="/leads", tags=["leads"])


@router.post("", response_model=LeadResponse)
def create_lead(payload: LeadCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    extraction = extract_entities(payload.raw_message)
    score = score_lead(extraction.intent, extraction.budget, extraction.timeline)

    existing = None
    if payload.email or payload.phone:
        conditions = []
        if payload.email:
            conditions.append(Lead.email == payload.email)
        if payload.phone:
            conditions.append(Lead.phone == payload.phone)
        existing = db.query(Lead).filter(or_(*conditions)).order_by(Lead.created_at.desc()).first()

    if existing:
        existing.raw_message = f"{existing.raw_message}\n---\n{payload.raw_message}".strip()
        existing.score = max(existing.score, score)
        existing.property_type = extraction.property_type or existing.property_type
        existing.location = extraction.location or existing.location
        existing.budget = extraction.budget or existing.budget
        existing.timeline = extraction.timeline or existing.timeline
        db.commit()
        db.refresh(existing)
        audit_event(db, "lead_merge", "lead", user_id=current_user.id, details=f"lead_id={existing.id}")
        return existing

    lead = Lead(
        full_name=payload.full_name,
        email=payload.email,
        phone=payload.phone,
        channel=payload.channel,
        raw_message=payload.raw_message,
        score=score,
        property_type=extraction.property_type,
        location=extraction.location,
        budget=extraction.budget,
        timeline=extraction.timeline,
    )
    db.add(lead)
    db.flush()

    lead.assigned_agent_id = assign_best_agent(db, lead)

    db.commit()
    db.refresh(lead)

    if lead.status == LeadStatus.new:
        send_followup_message.delay(lead.id, lead.channel.value, "Thanks for reaching out. We will contact you shortly.")

    audit_event(db, "lead_create", "lead", user_id=current_user.id, details=f"lead_id={lead.id}")
    return lead


@router.get("", response_model=list[LeadResponse])
def list_leads(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    query = db.query(Lead)
    if current_user.role == UserRole.agent:
        query = query.filter(Lead.assigned_agent_id == current_user.id)
    return query.order_by(Lead.created_at.desc()).all()


@router.patch("/{lead_id}", response_model=LeadResponse)
def update_lead(
    lead_id: int,
    payload: LeadUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin, UserRole.manager)),
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    if payload.status is not None:
        lead.status = payload.status
    if payload.assigned_agent_id is not None:
        lead.assigned_agent_id = payload.assigned_agent_id

    db.commit()
    db.refresh(lead)
    audit_event(db, "lead_update", "lead", user_id=current_user.id, details=f"lead_id={lead.id}")
    return lead


@router.get("/{lead_id}/recommendations")
def property_recommendations(
    lead_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    if current_user.role == UserRole.agent and lead.assigned_agent_id != current_user.id:
        raise HTTPException(status_code=403, detail="Agents can view recommendations only for assigned leads")

    properties = db.query(Property).filter(Property.is_available == True).all()
    ranked = []
    for prop in properties:
        score = 0.0
        if lead.property_type and prop.property_type.lower() == lead.property_type.lower():
            score += 45
        if lead.location and lead.location.lower() in prop.location.lower():
            score += 30
        if lead.budget and prop.price <= lead.budget:
            score += 25
        elif lead.budget:
            over_ratio = (prop.price - lead.budget) / lead.budget if lead.budget else 1.0
            score += max(0.0, 20 - over_ratio * 20)
        else:
            score += 10

        ranked.append(
            {
                "id": prop.id,
                "title": prop.title,
                "description": prop.description,
                "property_type": prop.property_type,
                "location": prop.location,
                "price": prop.price,
                "image_url": prop.image_url,
                "match_score": round(min(score, 100.0), 2),
            }
        )

    ranked.sort(key=lambda x: x["match_score"], reverse=True)
    return ranked[:10]
