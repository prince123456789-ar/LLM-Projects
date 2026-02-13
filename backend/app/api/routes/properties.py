from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_roles
from app.models.property import Property
from app.models.user import User, UserRole
from app.schemas.property import PropertyCreate, PropertyResponse

router = APIRouter(prefix="/properties", tags=["properties"])


@router.post("", response_model=PropertyResponse)
def create_property(
    payload: PropertyCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.admin, UserRole.manager)),
):
    prop = Property(**payload.model_dump())
    db.add(prop)
    db.commit()
    db.refresh(prop)
    return prop


@router.get("", response_model=list[PropertyResponse])
def list_properties(db: Session = Depends(get_db)):
    return db.query(Property).filter(Property.is_available == True).order_by(Property.created_at.desc()).all()
