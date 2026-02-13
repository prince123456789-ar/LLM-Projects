import hashlib
from app.models.lead import Lead


def lead_fingerprint(lead: Lead) -> str:
    key = f"{lead.email or ''}|{lead.phone or ''}|{lead.full_name.lower()}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()
