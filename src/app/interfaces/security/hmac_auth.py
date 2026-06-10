"""HMAC-SHA256 authentication for trusted clients (e.g. ZAFIRA-CORE)."""

from __future__ import annotations

import json

from fastapi import Depends, HTTPException, Request, status

from app.config import Settings, get_settings
from app.infrastructure.security.hmac_verifier import HmacRequestVerifier, HmacVerificationError


def load_allowed_clients(settings: Settings) -> dict[str, str]:
    raw = settings.hmac_allowed_clients_json
    if raw is None or not str(raw).strip():
        raise RuntimeError(
            "HMAC_ALLOWED_CLIENTS is not configured; refusing to start without "
            'real credentials (e.g. \'{"zafira-core": "<secret>"}\')'
        )
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("HMAC_ALLOWED_CLIENTS must be valid JSON object") from exc
    if not isinstance(parsed, dict):
        raise ValueError("HMAC_ALLOWED_CLIENTS must be a JSON object")
    out: dict[str, str] = {}
    for k, v in parsed.items():
        if not isinstance(k, str) or not isinstance(v, str):
            raise ValueError("HMAC_ALLOWED_CLIENTS keys and values must be strings")
        out[k] = v
    return out


def get_hmac_verifier(settings: Settings = Depends(get_settings)) -> HmacRequestVerifier:
    clients = load_allowed_clients(settings)
    return HmacRequestVerifier(clients, clock_skew_seconds=settings.hmac_clock_skew_seconds)


async def verify_hmac_request(
    request: Request,
    verifier: HmacRequestVerifier = Depends(get_hmac_verifier),
) -> None:
    body = await request.body()
    client_id = request.headers.get("X-CLIENT-ID")
    timestamp = request.headers.get("X-TIMESTAMP")
    signature = request.headers.get("X-SIGNATURE")
    try:
        verifier.verify(
            raw_body=body,
            client_id=client_id,
            timestamp_raw=timestamp,
            signature=signature,
        )
    except HmacVerificationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=exc.detail,
        ) from exc
