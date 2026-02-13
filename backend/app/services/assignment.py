from sqlalchemy.orm import Session

from app.models.user import User, UserRole
from app.models.lead import Lead, LeadStatus


def assign_best_agent(db: Session, lead: Lead) -> int | None:
    agents = db.query(User).filter(User.role == UserRole.agent, User.is_active == True).all()
    if not agents:
        return None

    # Basic heuristic: assign to the agent with the fewest active leads.
    best_agent = None
    min_count = None
    for agent in agents:
        active_count = (
            db.query(Lead)
            .filter(
                Lead.assigned_agent_id == agent.id,
                Lead.status.in_([LeadStatus.new, LeadStatus.contacted, LeadStatus.qualified]),
            )
            .count()
        )
        if min_count is None or active_count < min_count:
            min_count = active_count
            best_agent = agent

    return best_agent.id if best_agent else None
