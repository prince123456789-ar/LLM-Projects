from pydantic import BaseModel


class DashboardMetrics(BaseModel):
    total_leads: int
    converted_leads: int
    conversion_rate: float
    avg_lead_score: float
    by_channel: dict[str, int]
    by_agent: dict[str, int]
    # Optional business metrics (estimates) for the UI chart.
    mrr_usd: int = 0
    profit_usd: int = 0
    losses_usd: int = 0


class TimeSeriesPoint(BaseModel):
    day: str
    mrr_usd: int
    profit_usd: int
    losses_usd: int
    leads_created: int
    leads_converted: int
    leads_lost: int
