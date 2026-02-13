from datetime import datetime
import smtplib
from email.message import EmailMessage

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.lead import Lead, LeadChannel
from app.models.report import ScheduledReport
from app.services.messaging import dispatch_message
from app.services.reports import analytics_pdf
from app.workers.celery_app import celery_app

settings = get_settings()


def _send_email(to_email: str, subject: str, body: str, attachment: bytes | None = None, attachment_name: str = "report.pdf"):
    if not settings.SMTP_HOST:
        return {"status": "smtp_not_configured"}

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM_EMAIL
    msg["To"] = to_email
    msg.set_content(body)

    if attachment:
        msg.add_attachment(attachment, maintype="application", subtype="pdf", filename=attachment_name)

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
            server.starttls()
            server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.send_message(msg)

    return {"status": "sent"}


@celery_app.task
def send_followup_message(lead_id: int, channel: str, content: str) -> dict:
    db = SessionLocal()
    try:
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            return {"status": "lead_not_found", "lead_id": lead_id}

        message_payload = {
            "lead_id": lead.id,
            "to": lead.phone or lead.email,
            "content": content,
            "name": lead.full_name,
            "timestamp": datetime.utcnow().isoformat(),
        }

        return dispatch_message(db, LeadChannel(channel), message_payload)
    finally:
        db.close()


@celery_app.task
def send_scheduled_report(report_id: int) -> dict:
    db = SessionLocal()
    try:
        report = db.query(ScheduledReport).filter(ScheduledReport.id == report_id).first()
        if not report:
            return {"status": "report_not_found", "report_id": report_id}

        pdf = analytics_pdf(db)
        result = _send_email(
            report.recipient_email,
            subject="Real Estate AI Scheduled Analytics Report",
            body="Attached is your scheduled analytics report.",
            attachment=pdf,
            attachment_name="analytics.pdf",
        )
        return {"report_id": report.id, **result}
    finally:
        db.close()


@celery_app.task
def send_daily_agent_summary(agent_email: str, summary_text: str) -> dict:
    result = _send_email(
        agent_email,
        subject="Daily Lead Summary",
        body=summary_text,
    )
    return {"agent_email": agent_email, **result}
