import re
from dataclasses import dataclass


@dataclass
class ExtractionResult:
    property_type: str | None
    location: str | None
    budget: float | None
    timeline: str | None
    intent: str


BUDGET_RE = re.compile(r"\$?([0-9]{2,3}(?:[,.][0-9]{3})+|[0-9]{5,8})")


def extract_entities(message: str) -> ExtractionResult:
    text = message.lower()

    property_type = None
    for candidate in ["apartment", "villa", "house", "condo", "office"]:
        if candidate in text:
            property_type = candidate
            break

    location = None
    if " in " in text:
        after_in = text.split(" in ", 1)[1].strip()
        location = after_in.split(" ")[0].strip(",.") if after_in else None

    budget = None
    match = BUDGET_RE.search(message)
    if match:
        budget = float(match.group(1).replace(",", "").replace(".", ""))

    timeline = None
    for t in ["immediately", "this month", "next month", "3 months", "6 months"]:
        if t in text:
            timeline = t
            break

    intent = "browsing"
    if any(k in text for k in ["book", "visit", "schedule", "ready", "buy", "rent now"]):
        intent = "serious"
    elif any(k in text for k in ["price", "details", "info", "inquire"]):
        intent = "inquiring"

    return ExtractionResult(property_type, location, budget, timeline, intent)


def score_lead(intent: str, budget: float | None, timeline: str | None) -> float:
    score = 30.0
    if intent == "serious":
        score += 35
    elif intent == "inquiring":
        score += 20

    if budget is not None and budget >= 100000:
        score += 20

    if timeline in {"immediately", "this month", "next month"}:
        score += 15

    return min(100.0, score)
