"""Test environment + shared helpers/fakes.

Env vars are forced (not setdefault) so HMAC tests sign with known credentials
regardless of the host shell or a local .env.
"""

import hashlib
import hmac
import os
import time

os.environ["AI_BACKEND"] = "stub"
os.environ["HMAC_ALLOWED_CLIENTS"] = '{"zafira-core": "test-secret"}'
os.environ["HMAC_CLOCK_SKEW_SECONDS"] = "60"

TEST_CLIENT_ID = "zafira-core"
TEST_CLIENT_SECRET = "test-secret"


def hmac_headers(
    body: bytes,
    *,
    client_id: str = TEST_CLIENT_ID,
    secret: str = TEST_CLIENT_SECRET,
    timestamp: int | None = None,
) -> dict[str, str]:
    ts = str(int(time.time()) if timestamp is None else timestamp)
    message = body.decode() + ts
    signature = hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()
    return {"X-CLIENT-ID": client_id, "X-TIMESTAMP": ts, "X-SIGNATURE": signature}


class FakeImageFetcher:
    def __init__(self, payload: bytes = b"fake-image-bytes") -> None:
        self.payload = payload
        self.requested: list[str] = []

    async def fetch(self, url: str) -> bytes:
        self.requested.append(url)
        return self.payload


class InMemoryStorage:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    async def upload(self, *, key: str, data: bytes, content_type: str = "image/png") -> None:
        self.objects[key] = data
