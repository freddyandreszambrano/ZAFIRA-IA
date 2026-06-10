"""Guards of HttpImageFetcher exercised against a mocked transport (no network)."""

import httpx
import pytest

from app.domain.exceptions import DomainError
from app.infrastructure.http.image_fetcher import HttpImageFetcher

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"x" * 64


def _fetcher_with(handler, **kwargs) -> HttpImageFetcher:
    return HttpImageFetcher(transport=httpx.MockTransport(handler), **kwargs)


async def test_happy_path_returns_bytes():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=PNG_BYTES, headers={"content-type": "image/png"})

    result = await _fetcher_with(handler).fetch("https://storage.test/avatar.png")
    assert result == PNG_BYTES


async def test_non_200_raises_fetch_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, content=b"not found")

    with pytest.raises(DomainError) as exc:
        await _fetcher_with(handler).fetch("https://storage.test/missing.png")
    assert exc.value.code == "IMAGE_FETCH_ERROR"


async def test_non_image_content_type_rejected():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<html/>", headers={"content-type": "text/html"})

    with pytest.raises(DomainError) as exc:
        await _fetcher_with(handler).fetch("https://storage.test/page")
    assert exc.value.code == "IMAGE_INVALID_CONTENT_TYPE"


async def test_declared_content_length_over_limit_rejected_before_body():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=PNG_BYTES,
            headers={"content-type": "image/png", "content-length": str(10**9)},
        )

    with pytest.raises(DomainError) as exc:
        await _fetcher_with(handler, max_bytes=1024).fetch("https://storage.test/huge.png")
    assert exc.value.code == "IMAGE_TOO_LARGE"


async def test_streamed_body_over_limit_aborts():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * 2048, headers={"content-type": "image/png"})

    with pytest.raises(DomainError) as exc:
        await _fetcher_with(handler, max_bytes=1024).fetch("https://storage.test/liar.png")
    assert exc.value.code == "IMAGE_TOO_LARGE"


async def test_transport_error_wrapped_as_domain_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    with pytest.raises(DomainError) as exc:
        await _fetcher_with(handler).fetch("https://storage.test/down.png")
    assert exc.value.code == "IMAGE_FETCH_ERROR"
