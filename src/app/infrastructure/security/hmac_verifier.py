"""HMAC-SHA256 request verification (adapter; no FastAPI imports)."""

from __future__ import annotations

import hashlib
import hmac
import time
from collections.abc import Mapping


class HmacVerificationError(Exception):
    def __init__(self, detail: str) -> None:
        self.detail = detail
        super().__init__(detail)


class HmacRequestVerifier:
    """Validates X-CLIENT-ID / X-TIMESTAMP / X-SIGNATURE against raw body + timestamp string."""

    def __init__(
        self,
        allowed_clients: Mapping[str, str],
        *,
        clock_skew_seconds: int = 60,
    ) -> None:
        self._allowed = dict(allowed_clients)
        self._skew = clock_skew_seconds

    def verify(
        self,
        *,
        raw_body: bytes,
        client_id: str | None,
        timestamp_raw: str | None,
        signature: str | None,
    ) -> None:
        if client_id is None or not client_id.strip():
            raise HmacVerificationError("Missing X-CLIENT-ID")
        if timestamp_raw is None or not str(timestamp_raw).strip():
            raise HmacVerificationError("Missing X-TIMESTAMP")
        if signature is None or not str(signature).strip():
            raise HmacVerificationError("Missing X-SIGNATURE")

        secret = self._allowed.get(client_id)
        if secret is None:
            raise HmacVerificationError("Unknown client")

        try:
            ts = int(str(timestamp_raw).strip())
        except ValueError as exc:
            raise HmacVerificationError("Invalid X-TIMESTAMP") from exc

        now = int(time.time())
        if abs(now - ts) > self._skew:
            raise HmacVerificationError("Timestamp outside allowed window")

        try:
            body_text = raw_body.decode()
        except UnicodeDecodeError as exc:
            raise HmacVerificationError("Request body must be UTF-8") from exc

        message = body_text + str(timestamp_raw)
        expected = hmac.new(
            secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected, str(signature).strip()):
            raise HmacVerificationError("Invalid signature")
