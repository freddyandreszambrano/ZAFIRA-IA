"""Storage contract — keyed binary uploads, backend-agnostic."""

from typing import Protocol


class StorageClient(Protocol):
    async def upload(self, *, key: str, data: bytes, content_type: str = "image/png") -> None: ...
