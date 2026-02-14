from datetime import datetime, timedelta

from sqlalchemy import and_
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.billing import BillingSubscription, SubscriptionPlan, SubscriptionStatus
from app.models.lead import Lead, LeadStatus
from app.schemas.analytics import DashboardMetrics, TimeSeriesPoint


def get_dashboard_metrics(db: Session) -> DashboardMetrics:
    total = db.query(func.count(Lead.id)).scalar() or 0
    converted = db.query(func.count(Lead.id)).filter(Lead.status == LeadStatus.converted).scalar() or 0
    avg_score = db.query(func.avg(Lead.score)).scalar() or 0.0

    by_channel_rows = db.query(Lead.channel, func.count(Lead.id)).group_by(Lead.channel).all()
    by_channel = {str(row[0]): row[1] for row in by_channel_rows}

    by_agent_rows = db.query(Lead.assigned_agent_id, func.count(Lead.id)).group_by(Lead.assigned_agent_id).all()
    by_agent = {str(row[0] or "unassigned"): row[1] for row in by_agent_rows}

    rate = (converted / total * 100.0) if total else 0.0

    # Simple MRR estimate from subscriptions. Cap plan pricing at $199.
    plan_price = {
        SubscriptionPlan.starter: 0,
        SubscriptionPlan.agency: 99,
        SubscriptionPlan.pro: 199,
    }
    active_subs = (
        db.query(BillingSubscription.plan, func.count(BillingSubscription.id))
        .filter(BillingSubscription.status == SubscriptionStatus.active)
        .group_by(BillingSubscription.plan)
        .all()
    )
    mrr = 0
    for plan, cnt in active_subs:
        mrr += plan_price.get(plan, 0) * int(cnt or 0)

    # Losses estimate: "lost" leads are counted as opportunity loss with a small constant.
    lost = db.query(func.count(Lead.id)).filter(Lead.status == LeadStatus.lost).scalar() or 0
    losses = int(lost * 10)  # placeholder estimate; replace with your own model
    profit = max(0, int(mrr - losses))

    return DashboardMetrics(
        total_leads=total,
        converted_leads=converted,
        conversion_rate=round(rate, 2),
        avg_lead_score=round(float(avg_score), 2),
        by_channel=by_channel,
        by_agent=by_agent,
        mrr_usd=int(mrr),
        profit_usd=int(profit),
        losses_usd=int(losses),
    )


def get_timeseries(db: Session, days: int = 30) -> list[TimeSeriesPoint]:
    days = max(7, min(int(days or 30), 90))
    start = (datetime.utcnow() - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)

    plan_price = {
        SubscriptionPlan.starter: 0,
        SubscriptionPlan.agency: 99,
        SubscriptionPlan.pro: 199,
    }
    active_subs = (
        db.query(BillingSubscription.plan, func.count(BillingSubscription.id))
        .filter(BillingSubscription.status == SubscriptionStatus.active)
        .group_by(BillingSubscription.plan)
        .all()
    )
    mrr = 0
    for plan, cnt in active_subs:
        mrr += plan_price.get(plan, 0) * int(cnt or 0)

    points: list[TimeSeriesPoint] = []
    for i in range(days):
        day_start = start + timedelta(days=i)
        day_end = day_start + timedelta(days=1)

        created = (
            db.query(func.count(Lead.id))
            .filter(and_(Lead.created_at >= day_start, Lead.created_at < day_end))
            .scalar()
            or 0
        )
        converted = (
            db.query(func.count(Lead.id))
            .filter(and_(Lead.created_at >= day_start, Lead.created_at < day_end, Lead.status == LeadStatus.converted))
            .scalar()
            or 0
        )
        lost = (
            db.query(func.count(Lead.id))
            .filter(and_(Lead.created_at >= day_start, Lead.created_at < day_end, Lead.status == LeadStatus.lost))
            .scalar()
            or 0
        )

        losses = int(lost * 10)
        profit = max(0, int(mrr - losses))
        points.append(
            TimeSeriesPoint(
                day=day_start.date().isoformat(),
                mrr_usd=int(mrr),
                profit_usd=int(profit),
                losses_usd=int(losses),
                leads_created=int(created),
                leads_converted=int(converted),
                leads_lost=int(lost),
            )
        )

    return points
