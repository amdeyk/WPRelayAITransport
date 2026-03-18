from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from cli.lib.config import get_circuit_path


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def default_state() -> dict[str, Any]:
    return {
        "state": "CLOSED",
        "consecutive_failures": 0,
        "last_success_at": None,
        "last_failure_at": None,
        "last_failure": None,
        "history": [],
    }


def load_state(site_name: str) -> dict[str, Any]:
    path = get_circuit_path(site_name)
    if not path.exists():
        return default_state()
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_state(site_name: str, state: dict[str, Any]) -> None:
    path = get_circuit_path(site_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, sort_keys=True)
        handle.write("\n")


def can_execute(site_name: str, local_config: dict[str, Any], write_operation: bool) -> tuple[bool, str | None]:
    state = load_state(site_name)
    if not write_operation:
        if state["state"] == "OPEN" and local_config["circuit_breaker"].get("block_reads_when_open", False):
            return False, "Circuit breaker is OPEN and read operations are blocked."
        return True, None
    if state["state"] == "OPEN":
        return False, "Circuit breaker is OPEN. Reset it after fixing the underlying issue."
    return True, None


def _trim_old_failures(history: list[dict[str, Any]], window_minutes: int) -> list[dict[str, Any]]:
    cutoff = utc_now() - timedelta(minutes=window_minutes)
    return [item for item in history if datetime.fromisoformat(item["time"]) >= cutoff]


def register_result(site_name: str, local_config: dict[str, Any], status: str, detail: dict[str, Any]) -> dict[str, Any]:
    settings = local_config["circuit_breaker"]
    threshold = settings["consecutive_failure_threshold"]
    window_minutes = settings["failure_window_minutes"]
    partial_is_failure = settings.get("partial_counts_as_failure", True)

    state = load_state(site_name)
    state["history"] = _trim_old_failures(state.get("history", []), window_minutes)
    is_failure = status == "FAILED" or (status == "PARTIAL" and partial_is_failure)

    if is_failure:
        state["consecutive_failures"] = state.get("consecutive_failures", 0) + 1
        state["last_failure_at"] = utc_now().isoformat()
        state["last_failure"] = detail
        state["history"].append({"time": state["last_failure_at"], "status": status, "detail": detail})
        if state["consecutive_failures"] >= threshold:
            state["state"] = "OPEN"
        elif state["consecutive_failures"] == max(threshold - 1, 1):
            state["state"] = "HALF-OPEN"
        else:
            state["state"] = "CLOSED"
    else:
        state["state"] = "CLOSED"
        state["consecutive_failures"] = 0
        state["last_success_at"] = utc_now().isoformat()

    save_state(site_name, state)
    return state


def reset(site_name: str, local_config: dict[str, Any], pin: str) -> dict[str, Any]:
    expected = str(local_config["circuit_breaker"].get("human_pin", ""))
    if local_config["circuit_breaker"].get("human_pin_to_reset", True) and pin != expected:
        raise ValueError("Invalid reset PIN.")
    state = default_state()
    state["history"].append({"time": utc_now().isoformat(), "status": "RESET", "detail": {"reason": "human"}})
    save_state(site_name, state)
    return state

