from fastapi import APIRouter

from app.api.routes import analytics, api_keys, appointments, audit, auth, billing, integrations, leads, password_reset, properties, reports

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(leads.router)
api_router.include_router(properties.router)
api_router.include_router(analytics.router)
api_router.include_router(integrations.router)
api_router.include_router(appointments.router)
api_router.include_router(reports.router)
api_router.include_router(billing.router)
api_router.include_router(audit.router)
api_router.include_router(api_keys.router)
api_router.include_router(password_reset.router)
