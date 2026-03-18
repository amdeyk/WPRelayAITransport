from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import click
from rich.console import Console

from cli.lib.checkpoint import create_remote_checkpoint, store_local_checkpoint
from cli.lib.circuit import can_execute, register_result
from cli.lib.config import load_local_config
from cli.lib.http import WrsClient
from cli.lib.journal import start_operation, update_operation
from cli.lib.telemetry import classify_outcome


console = Console()


def get_site_context(site_name: str | None = None) -> tuple[dict, WrsClient]:
    local_config = load_local_config(site_name)
    client = WrsClient(local_config)
    return local_config, client


def payload_hash(payload: dict) -> str:
    rendered = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def ensure_write_allowed(site_name: str, local_config: dict) -> None:
    allowed, reason = can_execute(site_name, local_config, write_operation=True)
    if not allowed:
        raise click.ClickException(reason or "Circuit breaker blocked this operation.")


def run_write_operation(
    site_name: str,
    local_config: dict,
    client: WrsClient,
    op_type: str,
    endpoint: str,
    payload: dict,
    checkpoint_targets: dict | None = None,
    operator: str = "human",
    payload_summary: str | None = None,
    retry_of: str | None = None,
    ai_session_id: str | None = None,
) -> dict:
    ensure_write_allowed(site_name, local_config)
    journal_entry = start_operation(
        site_name,
        op_type=op_type,
        endpoint=endpoint,
        payload_hash=payload_hash(payload),
        operator=operator,
        payload_summary=payload_summary,
        retry_of=retry_of,
        ai_session_id=ai_session_id,
    )
    op_id = journal_entry["op_id"]
    checkpoint_id = None

    if checkpoint_targets and local_config.get("checkpoint", {}).get("auto_checkpoint", True):
        checkpoint_response = create_remote_checkpoint(client, op_id=op_id, op_type=op_type, targets=checkpoint_targets)
        checkpoint = checkpoint_response.get("checkpoint", {})
        checkpoint_id = checkpoint.get("checkpoint_id")
        if checkpoint and local_config.get("checkpoint", {}).get("local_copy", True):
            store_local_checkpoint(site_name, checkpoint_response)
        update_operation(site_name, op_id, "IN_FLIGHT", checkpoint_id=checkpoint_id)
    else:
        update_operation(site_name, op_id, "IN_FLIGHT")

    request_payload = dict(payload)
    request_payload["op_id"] = op_id
    response = client.request("POST", endpoint, payload=request_payload, operator=operator)
    status, telemetry = classify_outcome(response)
    update_operation(
        site_name,
        op_id,
        status,
        checkpoint_id=checkpoint_id,
        server_outcome=response,
        telemetry=telemetry,
    )
    register_result(site_name, local_config, status, {"endpoint": endpoint, "op_id": op_id, "response": response})
    return response


def resolve_project_file(local_config: dict, relative_path: str) -> Path:
    path = Path(relative_path)
    if path.is_absolute():
        return path
    return Path(os.path.expanduser(local_config["project_path"])) / path
