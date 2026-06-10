"""HTTP image download with content-type and size guards."""

from __future__ import annotations

from typing import Protocol

import httpx

from app.domain.exceptions import DomainError

_MAX_IMAGE_BYTES = 15 * 1024 * 1024


class ImageFetcher(Protocol):
    async def fetch(self, url: str) -> bytes: ...


class HttpImageFetcher:
    def __init__(
        self,
        *,
        timeout_seconds: float = 30.0,
        max_bytes: int = _MAX_IMAGE_BYTES,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._timeout = timeout_seconds
        self._max_bytes = max_bytes
        self._transport = transport

    async def fetch(self, url: str) -> bytes:
        try:
            async with (
                httpx.AsyncClient(
                    timeout=self._timeout, follow_redirects=True, transport=self._transport
                ) as client,
                client.stream("GET", url) as response,
            ):
                if response.status_code != 200:
                    raise DomainError(
                        f"Image URL returned HTTP {response.status_code}", "IMAGE_FETCH_ERROR"
                    )

                content_type = (
                    response.headers.get("content-type", "").split(";")[0].strip().lower()
                )
                if not content_type.startswith("image/"):
                    raise DomainError(
                        f"URL did not return an image (got '{content_type or 'unknown'}')",
                        "IMAGE_INVALID_CONTENT_TYPE",
                    )

                declared_length = response.headers.get("content-length", "")
                if declared_length.isdigit() and int(declared_length) > self._max_bytes:
                    raise DomainError("Image exceeds the allowed size", "IMAGE_TOO_LARGE")

                # Stream + cota incremental: nunca bufferizar más de max_bytes en RAM,
                # incluso si el servidor miente u omite Content-Length.
                buffer = bytearray()
                async for chunk in response.aiter_bytes():
                    buffer.extend(chunk)
                    if len(buffer) > self._max_bytes:
                        raise DomainError("Image exceeds the allowed size", "IMAGE_TOO_LARGE")
                return bytes(buffer)
        except httpx.HTTPError as exc:
            raise DomainError(f"Could not download image: {exc}", "IMAGE_FETCH_ERROR") from exc
