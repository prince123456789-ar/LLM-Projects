from datetime import datetime
from pydantic import BaseModel


class PropertyCreate(BaseModel):
    title: str
    description: str
    property_type: str
    location: str
    price: float
    image_url: str | None = None


class PropertyResponse(BaseModel):
    id: int
    title: str
    description: str
    property_type: str
    location: str
    price: float
    image_url: str | None
    is_available: bool
    created_at: datetime

    class Config:
        from_attributes = True
