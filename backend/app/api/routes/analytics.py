from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_roles
from app.models.user import User, UserRole
from app.schemas.analytics import DashboardMetrics, TimeSeriesPoint
from app.services.analytics import get_dashboard_metrics, get_timeseries

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/dashboard", response_model=DashboardMetrics)
def dashboard_metrics(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.admin, UserRole.manager)),
):
    return get_dashboard_metrics(db)


@router.get("/timeseries", response_model=list[TimeSeriesPoint])
def analytics_timeseries(
    days: int = Query(default=30, ge=7, le=90),
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.admin, UserRole.manager)),
):
    return get_timeseries(db, days=days)
