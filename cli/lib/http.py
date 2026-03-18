from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any

import requests


class WrsHttpError(RuntimeError):
    pass


def canonical_payload(payload: dict[str, Any] | None) -> str:
    if payload is None:
        return ""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def build_signature(token: str, path: str, timestamp: int, payload: dict[str, Any] | None) -> str:
    message = f"{path}|{timestamp}|{canonical_payload(payload)}".encode("utf-8")
    return hmac.new(token.encode("utf-8"), message, hashlib.sha256).hexdigest()


class WrsClient:
    def __init__(self, local_config: dict[str, Any]) -> None:
        self.local_config = local_config
        self.site_url = local_config["site_url"].rstrip("/")
        self.token = local_config["token"]
        self.timeout = 30

    def _headers(
        self,
        path: str,
        signature_payload: dict[str, Any] | None,
        operator: str,
    ) -> dict[str, str]:
        timestamp = int(time.time())
        return {
            "Content-Type": "application/json",
            "X-WRS-Token": self.token,
            "X-WRS-Time": str(timestamp),
            "X-WRS-Signature": build_signature(self.token, path, timestamp, signature_payload),
            "X-WRS-Operator": operator,
        }

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        operator: str = "human",
    ) -> dict[str, Any]:
        url = f"{self.site_url}/wp-json/wrs/v1{path}"
        signature_payload = payload if payload is not None else params
        headers = self._headers(path, signature_payload, operator)
        try:
            response = requests.request(
                method=method.upper(),
                url=url,
                headers=headers,
                json=payload if payload is not None else None,
                params=params,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise WrsHttpError(str(exc)) from exc

        try:
            data = response.json()
        except ValueError:
            body = response.text[:500]
            raise WrsHttpError(f"Non-JSON response ({response.status_code}): {body}")

        if response.status_code >= 400:
            message = data.get("message") or data.get("error") or f"HTTP {response.status_code}"
            raise WrsHttpError(message)
        return data
