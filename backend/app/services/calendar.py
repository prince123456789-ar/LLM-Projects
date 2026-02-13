from typing import Any

import requests
from sqlalchemy.orm import Session

from app.models.integration import CalendarIntegration


def push_calendar_event(
    db: Session,
    user_id: int,
    summary: str,
    description: str,
    start_iso: str,
    end_iso: str,
) -> dict[str, Any]:
    integration = db.query(CalendarIntegration).filter(CalendarIntegration.user_id == user_id).first()
    if not integration or not integration.is_active:
        return {"status": "not_configured"}

    # Minimal outbound adapter; production should exchange refresh token -> access token.
    if not integration.refresh_token_ref:
        return {"status": "missing_token"}

    url = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
    payload = {
        "summary": summary,
        "description": description,
        "start": {"dateTime": start_iso},
        "end": {"dateTime": end_iso},
    }
    headers = {
        "Authorization": f"Bearer {integration.refresh_token_ref}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(url, json=payload, headers=headers, timeout=15)
        if not response.ok:
            return {"status": "failed", "code": response.status_code, "detail": response.text}
        data = response.json()
        return {"status": "created", "event_id": data.get("id")}
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}
