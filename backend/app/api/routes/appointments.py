from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.models.appointment import Appointment
from app.models.lead import Lead
from app.models.user import User, UserRole
from app.schemas.appointment import AppointmentCreate, AppointmentResponse, AppointmentStatusUpdate
from app.services.calendar import push_calendar_event
from app.services.scheduling import suggest_next_slots

router = APIRouter(prefix="/appointments", tags=["appointments"])


@router.get("/suggestions")
def get_suggestions(_: User = Depends(get_current_user)):
    slots = suggest_next_slots()
    return [{"start_at": s[0], "end_at": s[1]} for s in slots]


@router.post("", response_model=AppointmentResponse)
def create_appointment(
    payload: AppointmentCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.admin, UserRole.manager, UserRole.agent)),
):
    lead = db.query(Lead).filter(Lead.id == payload.lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    if payload.end_at <= payload.start_at:
        raise HTTPException(status_code=400, detail="end_at must be after start_at")

    appt = Appointment(**payload.model_dump())
    db.add(appt)
    db.flush()

    calendar_result = push_calendar_event(
        db,
        payload.agent_id,
        summary=f"Property consultation: {lead.full_name}",
        description=lead.raw_message[:400],
        start_iso=payload.start_at.isoformat(),
        end_iso=payload.end_at.isoformat(),
    )
    if calendar_result.get("event_id"):
        appt.external_event_id = calendar_result["event_id"]

    db.commit()
    db.refresh(appt)
    return appt


@router.get("", response_model=list[AppointmentResponse])
def list_appointments(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    q = db.query(Appointment)
    if current_user.role == UserRole.agent:
        q = q.filter(Appointment.agent_id == current_user.id)
    return q.order_by(Appointment.start_at.desc()).all()


@router.patch("/{appointment_id}", response_model=AppointmentResponse)
def update_appointment_status(
    appointment_id: int,
    payload: AppointmentStatusUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.admin, UserRole.manager, UserRole.agent)),
):
    item = db.query(Appointment).filter(Appointment.id == appointment_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Appointment not found")

    item.status = payload.status
    db.commit()
    db.refresh(item)
    return item
