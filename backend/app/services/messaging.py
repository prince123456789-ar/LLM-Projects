import json
from typing import Any

import requests
from sqlalchemy.orm import Session

from app.models.integration import ChannelIntegration
from app.models.lead import LeadChannel
from app.services.meta import parse_integration_metadata, send_meta_message


def get_integration(db: Session, channel: LeadChannel) -> ChannelIntegration | None:
    return db.query(ChannelIntegration).filter(ChannelIntegration.channel == channel).first()


def dispatch_message(db: Session, channel: LeadChannel, payload: dict[str, Any]) -> dict[str, Any]:
    integration = get_integration(db, channel)
    if not integration:
        return {"status": "not_configured", "channel": channel.value}

    metadata = parse_integration_metadata(integration.metadata_json)

    if integration.provider_name.lower() == "meta":
        if not integration.api_key_ref:
            return {"status": "not_configured", "detail": "Meta access token missing in api_key_ref"}
        return send_meta_message(channel.value, integration.api_key_ref, metadata, payload)

    if not integration.webhook_url:
        return {"status": "not_configured", "channel": channel.value}

    headers = {"Content-Type": "application/json"}
    if integration.api_key_ref:
        headers["Authorization"] = f"Bearer {integration.api_key_ref}"

    try:
        response = requests.post(integration.webhook_url, data=json.dumps(payload), headers=headers, timeout=15)
        return {
            "status": "sent" if response.ok else "failed",
            "code": response.status_code,
            "channel": channel.value,
        }
    except Exception as exc:
        return {"status": "error", "channel": channel.value, "detail": str(exc)}
