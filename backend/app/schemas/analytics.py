from pydantic import BaseModel


class DashboardMetrics(BaseModel):
    total_leads: int
    converted_leads: int
    conversion_rate: float
    avg_lead_score: float
    by_channel: dict[str, int]
    by_agent: dict[str, int]
