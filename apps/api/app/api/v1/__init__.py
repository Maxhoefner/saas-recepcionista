from fastapi import APIRouter

from app.api.v1 import (
    ai_settings,
    appointments,
    auth,
    businesses,
    conversations,
    customers,
    faqs,
    health,
    professionals,
    schedules,
    services,
    whatsapp_account,
    whatsapp_webhook,
)

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router)
api_router.include_router(businesses.router)
api_router.include_router(services.router)
api_router.include_router(professionals.router)
api_router.include_router(schedules.router)
api_router.include_router(customers.router)
api_router.include_router(appointments.router)
api_router.include_router(ai_settings.router)
api_router.include_router(faqs.router)
api_router.include_router(conversations.router)
api_router.include_router(whatsapp_account.router)
api_router.include_router(whatsapp_webhook.router)
