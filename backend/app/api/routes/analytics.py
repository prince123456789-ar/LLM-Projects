from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.analytics import DashboardMetrics, TimeSeriesPoint
from app.services.analytics import get_dashboard_metrics, get_timeseries

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/dashboard", response_model=DashboardMetrics)
def dashboard_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_dashboard_metrics(db, current_user=current_user)


@router.get("/timeseries", response_model=list[TimeSeriesPoint])
def analytics_timeseries(
    days: int = Query(default=30, ge=7, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_timeseries(db, current_user=current_user, days=days)
