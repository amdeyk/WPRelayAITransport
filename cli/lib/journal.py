from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cli.lib.config import get_journal_path


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_record(site_name: str, record: dict[str, Any]) -> None:
    path = get_journal_path(site_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True))
        handle.write("\n")


def start_operation(
    site_name: str,
    op_type: str,
    endpoint: str,
    payload_hash: str,
    operator: str = "human",
    payload_summary: str | None = None,
    retry_of: str | None = None,
    ai_session_id: str | None = None,
) -> dict[str, Any]:
    entry = {
        "event": "OPERATION",
        "event_time": utc_now(),
        "op_id": str(uuid.uuid4()),
        "op_type": op_type,
        "endpoint": endpoint,
        "operator": operator,
        "payload_hash": payload_hash,
        "payload_summary": payload_summary,
        "retry_of": retry_of,
        "ai_session_id": ai_session_id,
        "status": "PENDING",
    }
    append_record(site_name, entry)
    return entry


def update_operation(site_name: str, op_id: str, status: str, **fields: Any) -> dict[str, Any]:
    entry = {
        "event": "OPERATION_STATUS",
        "event_time": utc_now(),
        "op_id": op_id,
        "status": status,
    }
    entry.update(fields)
    append_record(site_name, entry)
    return entry


def list_latest(site_name: str, limit: int = 10) -> list[dict[str, Any]]:
    merged = collapse_operations(site_name)
    return list(merged.values())[-limit:][::-1]


def read_records(site_name: str) -> list[dict[str, Any]]:
    path = get_journal_path(site_name)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def collapse_operations(site_name: str) -> dict[str, dict[str, Any]]:
    lines = read_records(site_name)
    merged: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for line in lines:
        record = line
        op_id = record.get("op_id")
        if not op_id:
            continue
        current = merged.setdefault(op_id, {})
        current.update(record)
        if op_id not in order:
            order.append(op_id)
    return {item: merged[item] for item in order}


def get_operation(site_name: str, op_id: str) -> dict[str, Any] | None:
    return collapse_operations(site_name).get(op_id)


def export_operations(site_name: str) -> list[dict[str, Any]]:
    return list(collapse_operations(site_name).values())


def journal_exists(site_name: str) -> bool:
    return Path(get_journal_path(site_name)).exists()
