"""Try-on use case — fetch person + garment images, run the model, persist the result."""

from __future__ import annotations

from app.application.dto.tryon import TryOnRequest, TryOnResponse
from app.infrastructure.ai.base import TryOnModel
from app.infrastructure.http.image_fetcher import ImageFetcher
from app.infrastructure.storage.base import StorageClient


class GenerateTryOnUseCase:
    def __init__(self, *, fetcher: ImageFetcher, model: TryOnModel, storage: StorageClient) -> None:
        self._fetcher = fetcher
        self._model = model
        self._storage = storage

    async def execute(self, request: TryOnRequest) -> TryOnResponse:
        person_image = await self._fetcher.fetch(str(request.person_image_url))
        garment_image = await self._fetcher.fetch(str(request.garment_image_url))
        generated = await self._model.generate(
            person_image=person_image,
            garment_image=garment_image,
            garment_type=request.garment_type,
            params=request.params,
        )

        key = f"tryons/{request.external_ref}.png"
        await self._storage.upload(key=key, data=generated, content_type="image/png")

        return TryOnResponse(
            external_ref=request.external_ref,
            result_image_key=key,
            meta={"model": type(self._model).__name__, "size_bytes": len(generated)},
        )
