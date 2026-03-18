from __future__ import annotations


def classify_outcome(response: dict) -> tuple[str, dict]:
    telemetry = response.get("telemetry", {})
    explicit_status = response.get("status")
    if explicit_status in {"SUCCESS", "FAILED", "PARTIAL"}:
        return explicit_status, telemetry

    if response.get("success") is False:
        return "FAILED", telemetry

    warnings = telemetry.get("warnings", [])
    if warnings:
        return "PARTIAL", telemetry
    return "SUCCESS", telemetry


def summarize(response: dict) -> str:
    status, telemetry = classify_outcome(response)
    php_errors = telemetry.get("php_errors", [])
    if php_errors:
        return f"{status} with {len(php_errors)} PHP error(s)"
    return status

