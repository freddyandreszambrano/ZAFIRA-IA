"""OpenAPI: document ZAFIRA-CORE HMAC headers on `/api/v1/*` operations."""

from __future__ import annotations

from typing import Any

_HMAC_SECURITY_SCHEMES: dict[str, dict[str, str]] = {
    "HmacClientId": {
        "type": "apiKey",
        "in": "header",
        "name": "X-CLIENT-ID",
        "description": "Registered client id for HMAC (e.g. `zafira-core`).",
    },
    "HmacTimestamp": {
        "type": "apiKey",
        "in": "header",
        "name": "X-TIMESTAMP",
        "description": "Unix epoch seconds; must be within server clock skew.",
    },
    "HmacSignature": {
        "type": "apiKey",
        "in": "header",
        "name": "X-SIGNATURE",
        "description": "Lowercase hex HMAC-SHA256 of `UTF-8(body) + X-TIMESTAMP`.",
    },
}


def _hmac_security_requirement() -> dict[str, list[str]]:
    return {"HmacClientId": [], "HmacTimestamp": [], "HmacSignature": []}


def apply_hmac_security_to_openapi(schema: dict[str, Any], api_v1_prefix: str) -> None:
    components = schema.setdefault("components", {})
    components.setdefault("securitySchemes", {}).update(_HMAC_SECURITY_SCHEMES)

    prefix = api_v1_prefix.rstrip("/") or "/"
    paths = schema.get("paths")
    if not isinstance(paths, dict):
        return

    for path_key, path_item in paths.items():
        if not isinstance(path_item, dict) or not str(path_key).startswith(prefix):
            continue
        for method in ("get", "post", "put", "patch", "delete", "head", "options"):
            op = path_item.get(method)
            if not isinstance(op, dict):
                continue
            req = _hmac_security_requirement()
            existing = op.get("security")
            if existing is None:
                op["security"] = [req]
            elif isinstance(existing, list) and req not in existing:
                op["security"] = [req, *existing]
