import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import get_current_user, require_roles
from app.models.billing import BillingSubscription, SubscriptionPlan, SubscriptionStatus
from app.models.user import User, UserRole
from app.services.audit import audit_event
from app.services.plans import PLAN_API_KEY_LIMIT, Feature, PLAN_FEATURES
from app.models.api_key import ApiKey
from app.core.security import api_key_hash, generate_api_key

router = APIRouter(prefix="/billing", tags=["billing"])


def _set_stripe_key() -> None:
    settings = get_settings()
    if settings.STRIPE_SECRET_KEY:
        stripe.api_key = settings.STRIPE_SECRET_KEY


def _stripe_config_ok(settings) -> tuple[bool, str]:
    if not settings.STRIPE_SECRET_KEY or not settings.STRIPE_SECRET_KEY.startswith("sk_"):
        return False, "Stripe secret key is missing/invalid (expected sk_...)"
    if not (settings.STRIPE_PRICE_ID or settings.STRIPE_PRICE_ID_AGENCY or settings.STRIPE_PRICE_ID_PRO):
        return False, "Stripe price id(s) missing (set STRIPE_PRICE_ID_AGENCY/PRO)"
    return True, ""


@router.get("/config")
def billing_config():
    """
    Diagnostics endpoint (no secrets) to explain why checkout fails.
    """
    s = get_settings()
    def valid_price(v: str) -> bool:
        return bool(v) and str(v).startswith("price_")
    return {
        "stripe_secret_key_present": bool(s.STRIPE_SECRET_KEY),
        "stripe_secret_key_prefix": (s.STRIPE_SECRET_KEY[:3] if s.STRIPE_SECRET_KEY else ""),
        "stripe_price_id_valid": valid_price(s.STRIPE_PRICE_ID),
        "stripe_price_id_agency_valid": valid_price(s.STRIPE_PRICE_ID_AGENCY),
        "stripe_price_id_pro_valid": valid_price(s.STRIPE_PRICE_ID_PRO),
        "success_url": s.STRIPE_SUCCESS_URL,
        "cancel_url": s.STRIPE_CANCEL_URL,
    }


@router.post("/checkout")
def create_checkout_session(
    plan: str = Query(default="agency", pattern="^(agency|pro)$"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin, UserRole.manager)),
):
    settings = get_settings()
    ok, msg = _stripe_config_ok(settings)
    if not ok:
        raise HTTPException(status_code=503, detail=f"Stripe not configured: {msg}")

    # Prefer explicit plan-specific price IDs; fallback to STRIPE_PRICE_ID.
    price_id = ""
    if plan == "agency":
        price_id = settings.STRIPE_PRICE_ID_AGENCY or settings.STRIPE_PRICE_ID
    elif plan == "pro":
        price_id = settings.STRIPE_PRICE_ID_PRO or settings.STRIPE_PRICE_ID
    if not price_id or not str(price_id).startswith("price_"):
        raise HTTPException(
            status_code=503,
            detail="Stripe not configured: invalid price id for plan (expected price_...). Check /api/v1/billing/config",
        )

    _set_stripe_key()

    customer_id = current_user.stripe_customer_id
    try:
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
    except stripe.error.StripeError:
        raise HTTPException(status_code=502, detail="Stripe checkout failed (verify keys/prices in .env)")

    audit_event(db, "billing_checkout_create", "billing", user_id=current_user.id)
    return {"checkout_url": session.get("url"), "session_id": session.get("id")}


@router.post("/portal")
def create_customer_portal(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin, UserRole.manager)),
):
    settings = get_settings()
    ok, msg = _stripe_config_ok(settings)
    if not ok:
        raise HTTPException(status_code=503, detail=f"Stripe not configured: {msg}")
    if not current_user.stripe_customer_id:
        raise HTTPException(status_code=400, detail="No Stripe customer linked")

    _set_stripe_key()
    try:
        session = stripe.billing_portal.Session.create(
            customer=current_user.stripe_customer_id,
            return_url=settings.STRIPE_SUCCESS_URL,
        )
    except stripe.error.StripeError:
        raise HTTPException(status_code=502, detail="Stripe portal failed")
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
        "auto_renew_enabled": bool(sub.auto_renew_enabled) if sub else True,
    }


@router.post("/auto-renew")
def set_auto_renew(
    enabled: bool = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(UserRole.admin, UserRole.manager)),
):
    settings = get_settings()
    ok, msg = _stripe_config_ok(settings)
    if not ok:
        raise HTTPException(status_code=503, detail=f"Stripe not configured: {msg}")

    sub = db.query(BillingSubscription).filter(BillingSubscription.user_id == current_user.id).order_by(BillingSubscription.created_at.desc()).first()
    if not sub or not sub.provider_subscription_id:
        raise HTTPException(status_code=400, detail="No subscription found")

    _set_stripe_key()
    # Stripe: cancel_at_period_end=True means auto-renew disabled.
    try:
        stripe.Subscription.modify(sub.provider_subscription_id, cancel_at_period_end=(not enabled))
    except stripe.error.StripeError:
        raise HTTPException(status_code=502, detail="Stripe auto-renew update failed")
    sub.auto_renew_enabled = 1 if enabled else 0
    db.commit()
    audit_event(db, "billing_auto_renew_set", "billing", user_id=current_user.id, details=f"enabled={enabled}")
    return {"status": "ok", "auto_renew_enabled": enabled}


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
            # Determine plan from price id if present.
            plan = SubscriptionPlan.starter
            try:
                items = (obj.get("items") or {}).get("data") or []
                price = (items[0].get("price") or {}).get("id") if items else None
            except Exception:
                price = None

            if price and settings.STRIPE_PRICE_ID_PRO and price == settings.STRIPE_PRICE_ID_PRO:
                plan = SubscriptionPlan.pro
            elif price and settings.STRIPE_PRICE_ID_AGENCY and price == settings.STRIPE_PRICE_ID_AGENCY:
                plan = SubscriptionPlan.agency
            elif status_raw in {"active", "trialing"}:
                # Fallback: treat any active subscription as agency if we can't map.
                plan = SubscriptionPlan.agency

            sub = db.query(BillingSubscription).filter(BillingSubscription.provider_subscription_id == sub_id).first()
            if not sub:
                sub = BillingSubscription(
                    user_id=user.id,
                    provider_subscription_id=sub_id,
                    provider_customer_id=customer_id,
                    status=mapped_status,
                    plan=plan,
                    auto_renew_enabled=0 if obj.get("cancel_at_period_end") else 1,
                )
                db.add(sub)
            else:
                sub.status = mapped_status
                sub.plan = plan
                sub.auto_renew_enabled = 0 if obj.get("cancel_at_period_end") else 1
            db.commit()
            audit_event(db, "billing_webhook_sync", "billing", user_id=user.id, details=f"event={event_type}")

            # When payment becomes active, ensure the user has an API key if plan allows it.
            if mapped_status == SubscriptionStatus.active and plan in PLAN_FEATURES and Feature.api_access in PLAN_FEATURES[plan]:
                existing_keys = db.query(ApiKey).filter(ApiKey.user_id == user.id, ApiKey.revoked_at.is_(None)).count()
                limit = PLAN_API_KEY_LIMIT.get(plan, 0)
                if existing_keys == 0 and limit > 0:
                    api_key = generate_api_key(get_settings().API_KEY_PREFIX)
                    prefix = api_key[:12]
                    db.add(ApiKey(user_id=user.id, prefix=prefix, key_hash=api_key_hash(api_key, get_settings().SECRET_KEY), name="Default"))
                    db.commit()

    return {"status": "ok"}
