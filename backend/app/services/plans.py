from enum import Enum

from app.models.billing import SubscriptionPlan


class Feature(str, Enum):
    leads = "leads"
    integrations = "integrations"
    reports = "reports"
    analytics = "analytics"
    api_access = "api_access"


PLAN_FEATURES: dict[SubscriptionPlan, set[Feature]] = {
    SubscriptionPlan.starter: {Feature.leads, Feature.analytics},
    SubscriptionPlan.agency: {Feature.leads, Feature.analytics, Feature.integrations, Feature.api_access},
    SubscriptionPlan.pro: {Feature.leads, Feature.analytics, Feature.integrations, Feature.reports, Feature.api_access},
}


PLAN_API_KEY_LIMIT: dict[SubscriptionPlan, int] = {
    SubscriptionPlan.starter: 0,
    SubscriptionPlan.agency: 1,
    SubscriptionPlan.pro: 3,
}
