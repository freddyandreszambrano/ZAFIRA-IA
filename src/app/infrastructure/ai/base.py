"""Model contracts — byte-in/byte-out so backends stay interchangeable."""

from typing import Any, Protocol


class AvatarModel(Protocol):
    async def generate(self, *, source_image: bytes, params: dict[str, Any]) -> bytes: ...


class TryOnModel(Protocol):
    async def generate(
        self,
        *,
        person_image: bytes,
        garment_image: bytes,
        garment_type: str,
        params: dict[str, Any],
    ) -> bytes: ...
