from __future__ import annotations

from cli.lib.circuit import load_state
from cli.lib.journal import list_latest


def build_context(site_name: str, local_config: dict, server_status: dict | None = None) -> dict:
    recent_journal = list_latest(site_name, limit=5)
    last_telemetry = recent_journal[0].get("telemetry") if recent_journal else {}
    pending_partial = [entry for entry in recent_journal if entry.get("status") == "PARTIAL"]
    active_warnings = []
    if last_telemetry:
        active_warnings = last_telemetry.get("warnings", []) + last_telemetry.get("php_errors", [])
    return {
        "site": site_name,
        "config_summary": {
            "page_mode": local_config.get("page_mode"),
            "css_mode": local_config.get("css_mode"),
            "modules": local_config.get("modules", {}),
        },
        "circuit_breaker": load_state(site_name),
        "recent_journal": recent_journal,
        "last_telemetry": last_telemetry,
        "pending_partial": pending_partial,
        "active_warnings": active_warnings,
        "site_inventory": server_status.get("site_inventory", {}) if server_status else {},
        "server_state": server_status or {},
    }
