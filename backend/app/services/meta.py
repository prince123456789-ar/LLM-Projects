import hashlib
import hmac
import json
from typing import Any

import requests


META_API_BASE = "https://graph.facebook.com"


def verify_meta_signature(app_secret: str, raw_body: bytes, signature_header: str | None) -> bool:
    if not app_secret or not signature_header:
        return False
    if not signature_header.startswith("sha256="):
        return False

    sent_sig = signature_header.split("=", 1)[1]
    calc_sig = hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(sent_sig, calc_sig)


def parse_integration_metadata(metadata_json: str | None) -> dict[str, Any]:
    if not metadata_json:
        return {}
    try:
        data = json.loads(metadata_json)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def parse_meta_messages(channel: str, payload: dict[str, Any]) -> list[dict[str, str | None]]:
    messages: list[dict[str, str | None]] = []

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})

            # WhatsApp Cloud API structure
            wa_contacts = value.get("contacts", [])
            wa_names = {
                c.get("wa_id"): (c.get("profile") or {}).get("name")
                for c in wa_contacts
                if c.get("wa_id")
            }

            for msg in value.get("messages", []):
                sender = msg.get("from")
                text = (msg.get("text") or {}).get("body")
                if sender and text:
                    messages.append(
                        {
                            "full_name": wa_names.get(sender) or sender,
                            "phone": sender if channel == "whatsapp" else None,
                            "message": text,
                        }
                    )

        # Messenger / Instagram structure
        for messaging_event in entry.get("messaging", []):
            sender_id = (messaging_event.get("sender") or {}).get("id")
            text = (messaging_event.get("message") or {}).get("text")
            if sender_id and text:
                messages.append(
                    {
                        "full_name": sender_id,
                        "phone": None,
                        "message": text,
                    }
                )

    return messages


def send_meta_message(channel: str, access_token: str, metadata: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    version = metadata.get("meta_api_version", "v21.0")
    recipient = payload.get("to")
    content = payload.get("content")
    if not recipient or not content:
        return {"status": "invalid_payload", "detail": "payload.to and payload.content are required"}

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    if channel == "whatsapp":
        phone_number_id = metadata.get("whatsapp_phone_number_id")
        if not phone_number_id:
            return {"status": "not_configured", "detail": "metadata.whatsapp_phone_number_id missing"}

        url = f"{META_API_BASE}/{version}/{phone_number_id}/messages"
        body = {
            "messaging_product": "whatsapp",
            "to": recipient,
            "type": "text",
            "text": {"body": content},
        }
        response = requests.post(url, headers=headers, json=body, timeout=20)
        return {
            "status": "sent" if response.ok else "failed",
            "code": response.status_code,
            "response": response.text,
        }

    if channel in {"facebook", "instagram"}:
        # Messenger endpoint for Page and IG messaging via Graph.
        # Depending on Meta app mode and channel setup, page/IG IDs and permissions must match.
        endpoint = f"{META_API_BASE}/{version}/me/messages"
        body = {
            "recipient": {"id": recipient},
            "message": {"text": content},
        }
        response = requests.post(endpoint, headers=headers, json=body, timeout=20)
        return {
            "status": "sent" if response.ok else "failed",
            "code": response.status_code,
            "response": response.text,
        }

    return {"status": "unsupported_channel", "channel": channel}
