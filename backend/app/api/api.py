from fastapi import APIRouter

from app.api.routes import analytics, appointments, auth, billing, integrations, leads, properties, reports

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(leads.router)
api_router.include_router(properties.router)
api_router.include_router(analytics.router)
api_router.include_router(integrations.router)
api_router.include_router(appointments.router)
api_router.include_router(reports.router)
api_router.include_router(billing.router)
