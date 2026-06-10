"""HMAC authentication tests against /api/v1/avatar."""

import json
import time

from fastapi.testclient import TestClient

from app.interfaces.dependencies import get_image_fetcher, get_storage_client
from app.main import app
from tests.conftest import FakeImageFetcher, InMemoryStorage, hmac_headers

client = TestClient(app)

_BODY = json.dumps(
    {
        "external_ref": "ref-1",
        "source_image_url": "https://media.example.com/selfie.jpg",
        "params": {},
    }
).encode()


def _post(headers: dict[str, str]):
    return client.post(
        "/api/v1/avatar",
        content=_BODY,
        headers={"Content-Type": "application/json", **headers},
    )


def test_missing_headers_rejected() -> None:
    response = _post({})
    assert response.status_code == 401
    assert "X-CLIENT-ID" in response.json()["detail"]


def test_unknown_client_rejected() -> None:
    response = _post(hmac_headers(_BODY, client_id="intruder"))
    assert response.status_code == 401


def test_invalid_signature_rejected() -> None:
    headers = hmac_headers(_BODY)
    headers["X-SIGNATURE"] = "0" * 64
    response = _post(headers)
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid signature"


def test_timestamp_outside_skew_rejected() -> None:
    stale = int(time.time()) - 3600
    response = _post(hmac_headers(_BODY, timestamp=stale))
    assert response.status_code == 401
    assert "window" in response.json()["detail"].lower()


def test_valid_signature_passes() -> None:
    app.dependency_overrides[get_image_fetcher] = FakeImageFetcher
    app.dependency_overrides[get_storage_client] = InMemoryStorage
    try:
        response = _post(hmac_headers(_BODY))
        assert response.status_code == 200
        assert response.json()["avatar_image_key"] == "avatars/ref-1.png"
    finally:
        app.dependency_overrides.clear()
