from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_roles
from app.models.user import User, UserRole
from app.schemas.analytics import DashboardMetrics
from app.services.analytics import get_dashboard_metrics

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/dashboard", response_model=DashboardMetrics)
def dashboard_metrics(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.admin, UserRole.manager)),
):
    return get_dashboard_metrics(db)
