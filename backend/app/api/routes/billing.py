import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.models.billing import BillingSubscription, SubscriptionStatus
from app.models.user import User, UserRole
from app.services.audit import audit_event

router = APIRouter(prefix="/billing", tags=["billing"])


def _set_stripe_key() -> None:
    settings = get_settings()
    if settings.STRIPE_SECRET_KEY:
        stripe.api_key = settings.STRIPE_SECRET_KEY


@router.post("/checkout")
def create_checkout_session(
    plan: str = Query(default="agency", pattern="^(agency|pro)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin, UserRole.manager)),
):
    settings = get_settings()
    if not settings.STRIPE_SECRET_KEY or not settings.STRIPE_PRICE_ID:
        raise HTTPException(status_code=503, detail="Stripe not configured")

    price_id = settings.STRIPE_PRICE_ID
    if plan == "agency" and settings.STRIPE_PRICE_ID_AGENCY:
        price_id = settings.STRIPE_PRICE_ID_AGENCY
    if plan == "pro" and settings.STRIPE_PRICE_ID_PRO:
        price_id = settings.STRIPE_PRICE_ID_PRO

    _set_stripe_key()

    customer_id = current_user.stripe_customer_id
    if not customer_id:
        customer = stripe.Customer.create(email=current_user.email, name=current_user.full_name)
        customer_id = customer["id"]
        current_user.stripe_customer_id = customer_id
        db.commit()

    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=settings.STRIPE_SUCCESS_URL,
        cancel_url=settings.STRIPE_CANCEL_URL,
    )

    audit_event(db, "billing_checkout_create", "billing", user_id=current_user.id)
    return {"checkout_url": session.get("url"), "session_id": session.get("id")}


@router.post("/portal")
def create_customer_portal(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin, UserRole.manager)),
):
    settings = get_settings()
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=503, detail="Stripe not configured")
    if not current_user.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No Stripe customer linked")

    _set_stripe_key()
    session = stripe.billing_portal.Session.create(
        customer=current_user.stripe_customer_id,
        return_url=settings.STRIPE_SUCCESS_URL,
    )
    return {"portal_url": session.get("url")}


@router.get("/status")
def billing_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin, UserRole.manager)),
):
    sub = db.query(BillingSubscription).filter(BillingSubscription.user_id == current_user.id).order_by(BillingSubscription.created_at.desc()).first()
    return {
        "has_customer": bool(current_user.stripe_customer_id),
        "plan": sub.plan.value if sub else "starter",
        "status": sub.status.value if sub else "trial",
        "provider_subscription_id": sub.provider_subscription_id if sub else None,
    }


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="stripe-signature"),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    payload = await request.body()
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="Stripe webhook secret not configured")

    _set_stripe_key()
    try:
        event = stripe.Webhook.construct_event(payload, stripe_signature, settings.STRIPE_WEBHOOK_SECRET)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Stripe signature")

    event_type = event.get("type", "")
    obj = event.get("data", {}).get("object", {})

    if event_type in {"customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted"}:
        customer_id = obj.get("customer")
        sub_id = obj.get("id")
        status_raw = obj.get("status", "")
        status_map = {
            "active": SubscriptionStatus.active,
            "trialing": SubscriptionStatus.trial,
            "past_due": SubscriptionStatus.past_due,
            "canceled": SubscriptionStatus.canceled,
            "unpaid": SubscriptionStatus.past_due,
        }
        mapped_status = status_map.get(status_raw, SubscriptionStatus.past_due)

        user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
        if user:
            sub = db.query(BillingSubscription).filter(BillingSubscription.provider_subscription_id == sub_id).first()
            if not sub:
                sub = BillingSubscription(
                    user_id=user.id,
                    provider_subscription_id=sub_id,
                    provider_customer_id=customer_id,
                    status=mapped_status,
                )
                db.add(sub)
            else:
                sub.status = mapped_status
            db.commit()
            audit_event(db, "billing_webhook_sync", "billing", user_id=user.id, details=f"event={event_type}")

    return {"status": "ok"}
