from fastapi import APIRouter, Depends

from app.application.use_cases.get_health import GetHealthUseCase
from app.interfaces.dependencies import get_get_health_use_case
from app.interfaces.schemas.health import HealthResponse

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    tags=["health"],
    summary="Health check",
)
async def health(use_case: GetHealthUseCase = Depends(get_get_health_use_case)) -> HealthResponse:
    dto = use_case.execute()
    return HealthResponse(status=dto.status, version=dto.version)
