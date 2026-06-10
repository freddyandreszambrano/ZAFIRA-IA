"""Avatar generation use case — fetch the source photo, run the model, persist the result."""

from __future__ import annotations

from app.application.dto.avatar import AvatarRequest, AvatarResponse
from app.infrastructure.ai.base import AvatarModel
from app.infrastructure.http.image_fetcher import ImageFetcher
from app.infrastructure.storage.base import StorageClient


class GenerateAvatarUseCase:
    def __init__(
        self, *, fetcher: ImageFetcher, model: AvatarModel, storage: StorageClient
    ) -> None:
        self._fetcher = fetcher
        self._model = model
        self._storage = storage

    async def execute(self, request: AvatarRequest) -> AvatarResponse:
        source_image = await self._fetcher.fetch(str(request.source_image_url))
        generated = await self._model.generate(source_image=source_image, params=request.params)

        key = f"avatars/{request.external_ref}.png"
        await self._storage.upload(key=key, data=generated, content_type="image/png")

        return AvatarResponse(
            external_ref=request.external_ref,
            avatar_image_key=key,
            meta={"model": type(self._model).__name__, "size_bytes": len(generated)},
        )
