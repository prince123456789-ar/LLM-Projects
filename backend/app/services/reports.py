from io import StringIO, BytesIO
import csv

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from sqlalchemy.orm import Session

from app.models.lead import Lead
from app.services.analytics import get_dashboard_metrics


def leads_csv(db: Session) -> str:
    rows = db.query(Lead).order_by(Lead.created_at.desc()).all()
    out = StringIO()
    writer = csv.writer(out)
    writer.writerow([
        "id",
        "full_name",
        "email",
        "phone",
        "channel",
        "status",
        "score",
        "property_type",
        "location",
        "budget",
        "timeline",
        "assigned_agent_id",
        "created_at",
    ])

    for l in rows:
        writer.writerow([
            l.id,
            l.full_name,
            l.email or "",
            l.phone or "",
            l.channel.value,
            l.status.value,
            l.score,
            l.property_type or "",
            l.location or "",
            l.budget or "",
            l.timeline or "",
            l.assigned_agent_id or "",
            l.created_at.isoformat(),
        ])

    return out.getvalue()


def analytics_pdf(db: Session) -> bytes:
    metrics = get_dashboard_metrics(db)

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    y = 760
    p.setFont("Helvetica-Bold", 16)
    p.drawString(50, y, "Real Estate AI - Analytics Report")
    y -= 40
    p.setFont("Helvetica", 11)

    lines = [
        f"Total Leads: {metrics.total_leads}",
        f"Converted Leads: {metrics.converted_leads}",
        f"Conversion Rate: {metrics.conversion_rate}%",
        f"Average Lead Score: {metrics.avg_lead_score}",
        f"By Channel: {metrics.by_channel}",
        f"By Agent: {metrics.by_agent}",
    ]

    for line in lines:
        p.drawString(50, y, line)
        y -= 22

    p.showPage()
    p.save()
    buffer.seek(0)
    return buffer.read()
