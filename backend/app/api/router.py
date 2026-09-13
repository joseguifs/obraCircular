from fastapi import APIRouter

from app.api.routes.enderecos import router as enderecos_router
from app.api.routes.health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(enderecos_router)
