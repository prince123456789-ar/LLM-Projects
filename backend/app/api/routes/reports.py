from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_roles
from app.models.report import ScheduledReport
from app.models.user import User, UserRole
from app.schemas.report import ScheduledReportCreate, ScheduledReportResponse
from app.services.reports import analytics_pdf, leads_csv
from app.workers.tasks import send_scheduled_report

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/leads.csv")
def export_leads_csv(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.admin, UserRole.manager)),
):
    csv_data = leads_csv(db)
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=leads.csv"},
    )


@router.get("/analytics.pdf")
def export_analytics_pdf(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.admin, UserRole.manager)),
):
    pdf = analytics_pdf(db)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=analytics.pdf"},
    )


@router.post("/scheduled", response_model=ScheduledReportResponse)
def create_scheduled_report(
    payload: ScheduledReportCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin, UserRole.manager)),
):
    item = ScheduledReport(
        frequency=payload.frequency,
        recipient_email=payload.recipient_email,
        report_type=payload.report_type,
        created_by_user_id=current_user.id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/scheduled", response_model=list[ScheduledReportResponse])
def list_scheduled_reports(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.admin, UserRole.manager)),
):
    return db.query(ScheduledReport).order_by(ScheduledReport.created_at.desc()).all()


@router.post("/scheduled/{report_id}/send-now")
def send_now(
    report_id: int,
    _: User = Depends(require_roles(UserRole.admin, UserRole.manager)),
):
    send_scheduled_report.delay(report_id)
    return {"status": "queued", "report_id": report_id}
