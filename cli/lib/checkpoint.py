from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cli.lib.config import get_checkpoint_dir


def create_remote_checkpoint(client: Any, op_id: str, op_type: str, targets: dict[str, Any]) -> dict[str, Any]:
    return client.request(
        "POST",
        "/checkpoint/create",
        payload={"op_id": op_id, "op_type": op_type, "targets": targets},
    )


def store_local_checkpoint(site_name: str, checkpoint_response: dict[str, Any]) -> Path:
    checkpoint_id = checkpoint_response["checkpoint"]["checkpoint_id"]
    path = get_checkpoint_dir(site_name) / f"{checkpoint_id}.json"
    with path.open("w", encoding="utf-8") as handle:
        json.dump(checkpoint_response["checkpoint"], handle, indent=2, sort_keys=True)
        handle.write("\n")
    return path


def list_local_checkpoints(site_name: str) -> list[dict[str, Any]]:
    checkpoints: list[dict[str, Any]] = []
    for path in sorted(get_checkpoint_dir(site_name).glob("*.json")):
        checkpoints.append(json.loads(path.read_text(encoding="utf-8")))
    return checkpoints


def read_local_checkpoint(site_name: str, checkpoint_id: str) -> dict[str, Any]:
    path = get_checkpoint_dir(site_name) / f"{checkpoint_id}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def rollback_remote_checkpoint(client: Any, checkpoint_id: str, dry_run: bool = False) -> dict[str, Any]:
    return client.request(
        "POST",
        "/checkpoint/rollback",
        payload={"checkpoint_id": checkpoint_id, "dry_run": dry_run},
    )
