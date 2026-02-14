import json
import re
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models.property import Property
from app.services.nlp import extract_entities


EMAIL_RE = re.compile(r"([A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,})", re.IGNORECASE)
PHONE_RE = re.compile(r"(\\+?\\d[\\d\\s().-]{7,}\\d)")


@dataclass
class AgentResult:
    reply: str
    extracted: dict
    recommendations: list[dict]


def _find_recommendations(db: Session, extracted: dict) -> list[dict]:
    props = db.query(Property).filter(Property.is_available == True).limit(50).all()
    ranked: list[tuple[float, Property]] = []
    ptype = (extracted.get("property_type") or "").strip().lower()
    loc = (extracted.get("location") or "").strip().lower()
    budget = extracted.get("budget")
    try:
        budget_v = float(budget) if budget is not None else None
    except Exception:
        budget_v = None

    for p in props:
        score = 0.0
        if ptype and p.property_type and p.property_type.lower() == ptype:
            score += 40
        if loc and p.location and loc in p.location.lower():
            score += 35
        if budget_v is not None:
            if p.price <= budget_v:
                score += 25
            else:
                score += max(0.0, 15 - ((p.price - budget_v) / max(budget_v, 1.0)) * 15)
        else:
            score += 8
        ranked.append((score, p))

    ranked.sort(key=lambda x: x[0], reverse=True)
    out: list[dict] = []
    for s, p in ranked[:5]:
        if s < 10:
            continue
        out.append({"id": p.id, "title": p.title, "location": p.location, "price": p.price, "image_url": p.image_url})
    return out


def agent_team_reply(db: Session, message: str) -> AgentResult:
    """
    Lightweight multi-agent behavior without external LLMs:
    - Intake: acknowledge and ask for missing criteria
    - Qualifier: extract entities, compute next questions
    - Recommender: return top matching properties
    """
    msg = (message or "").strip()
    extraction = extract_entities(msg)
    extracted = {
        "intent": extraction.intent,
        "property_type": extraction.property_type,
        "location": extraction.location,
        "budget": extraction.budget,
        "timeline": extraction.timeline,
    }

    email = None
    phone = None
    m = EMAIL_RE.search(msg)
    if m:
        email = m.group(1)
    p = PHONE_RE.search(msg)
    if p:
        phone = p.group(1)
    if email:
        extracted["email"] = email
    if phone:
        extracted["phone"] = phone

    missing = []
    if not extracted.get("location"):
        missing.append("location")
    if not extracted.get("property_type"):
        missing.append("property type")
    if extracted.get("budget") is None:
        missing.append("budget")

    recs = _find_recommendations(db, extracted)

    if missing:
        ask = ", ".join(missing)
        reply = (
            "I can help right now. "
            f"To match listings, tell me your {ask}."
        )
        if extracted.get("timeline"):
            reply += f" Timeline noted: {extracted.get('timeline')}."
        return AgentResult(reply=reply, extracted=extracted, recommendations=recs)

    reply = "Thanks. I found a few matching options. If you share your name and phone/email, an agent can confirm a viewing time."
    return AgentResult(reply=reply, extracted=extracted, recommendations=recs)


def meta_json(**kwargs) -> str:
    return json.dumps(kwargs, ensure_ascii=True, separators=(",", ":"))

