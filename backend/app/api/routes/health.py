from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health", summary="Verifica se a API está disponível")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
