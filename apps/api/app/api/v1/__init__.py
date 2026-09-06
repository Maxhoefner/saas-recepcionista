from fastapi import APIRouter

from app.api.v1 import auth, businesses, customers, health, professionals, schedules, services

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router)
api_router.include_router(businesses.router)
api_router.include_router(services.router)
api_router.include_router(professionals.router)
api_router.include_router(schedules.router)
api_router.include_router(customers.router)
