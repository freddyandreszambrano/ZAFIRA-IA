from fastapi import APIRouter

from app.interfaces.api.v1.avatar.router import router as avatar_router
from app.interfaces.api.v1.tryon.router import router as tryon_router
from app.interfaces.openapi_tags import OPENAPI_TAG_AVATAR, OPENAPI_TAG_TRYON

api_router = APIRouter()

api_router.include_router(avatar_router, prefix="/avatar", tags=[OPENAPI_TAG_AVATAR])
api_router.include_router(tryon_router, prefix="/tryon", tags=[OPENAPI_TAG_TRYON])
