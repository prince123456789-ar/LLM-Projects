from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.lead import Lead, LeadStatus
from app.schemas.analytics import DashboardMetrics


def get_dashboard_metrics(db: Session) -> DashboardMetrics:
    total = db.query(func.count(Lead.id)).scalar() or 0
    converted = db.query(func.count(Lead.id)).filter(Lead.status == LeadStatus.converted).scalar() or 0
    avg_score = db.query(func.avg(Lead.score)).scalar() or 0.0

    by_channel_rows = db.query(Lead.channel, func.count(Lead.id)).group_by(Lead.channel).all()
    by_channel = {str(row[0]): row[1] for row in by_channel_rows}

    by_agent_rows = db.query(Lead.assigned_agent_id, func.count(Lead.id)).group_by(Lead.assigned_agent_id).all()
    by_agent = {str(row[0] or "unassigned"): row[1] for row in by_agent_rows}

    rate = (converted / total * 100.0) if total else 0.0
    return DashboardMetrics(
        total_leads=total,
        converted_leads=converted,
        conversion_rate=round(rate, 2),
        avg_lead_score=round(float(avg_score), 2),
        by_channel=by_channel,
        by_agent=by_agent,
    )
