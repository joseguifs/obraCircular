from fastapi import APIRouter

from app.api.routes.anuncios import router as anuncios_router
from app.api.routes.anuncios import user_router as usuario_anuncios_router
from app.api.routes.health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(anuncios_router)
api_router.include_router(usuario_anuncios_router)
