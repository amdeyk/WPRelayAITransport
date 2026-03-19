from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any

import requests


class WrsHttpError(RuntimeError):
    pass


COMMON_JSON_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
}


def enrich_error_message(message: str, local_config: dict[str, Any]) -> str:
    normalized = message.strip().lower()
    if normalized in ("invalid token.", "invalid token"):
        site_name = local_config.get("site_name") or local_config.get("site_url", "this site")
        return (
            f"Invalid token for {site_name}. "
            "The local token does not match the WordPress server token. "
            "Recover by re-pairing with `python cli/wrs.py pair <code>` from WordPress Admin, "
            "or rotate the token with `python setup/wizard.py --rotate-token --site "
            f"{site_name}` and reinstall the generated plugin ZIP."
        )
    return message


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
            **COMMON_JSON_HEADERS,
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
            raise WrsHttpError(enrich_error_message(message, self.local_config))
        return data
