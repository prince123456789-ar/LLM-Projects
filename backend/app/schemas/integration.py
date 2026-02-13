from datetime import datetime

from pydantic import BaseModel

from app.models.integration import IntegrationStatus
from app.models.lead import LeadChannel


class ChannelIntegrationCreate(BaseModel):
    channel: LeadChannel
    provider_name: str
    webhook_url: str | None = None
    api_key_ref: str | None = None
    metadata_json: str | None = None


class ChannelIntegrationResponse(BaseModel):
    id: int
    channel: LeadChannel
    provider_name: str
    webhook_url: str | None
    api_key_ref: str | None
    status: IntegrationStatus
    metadata_json: str | None
    created_at: datetime

    class Config:
        from_attributes = True


class WebhookLeadIngest(BaseModel):
    full_name: str
    email: str | None = None
    phone: str | None = None
    message: str


class MetaSendMessageRequest(BaseModel):
    channel: LeadChannel
    recipient_id: str
    content: str


class MetaWebhookVerificationResponse(BaseModel):
    status: str
