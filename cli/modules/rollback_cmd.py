from __future__ import annotations

import click

from cli.lib.checkpoint import rollback_remote_checkpoint
from cli.lib.config import load_local_config
from cli.lib.journal import export_operations, get_operation
from cli.modules.common import console, get_site_context


def _resolve_checkpoint_id(site_name: str, op_id: str | None, last: bool) -> str:
    if op_id:
        entry = get_operation(site_name, op_id)
        if not entry or not entry.get("checkpoint_id"):
            raise click.ClickException(f"No checkpoint recorded for op_id {op_id}")
        return str(entry["checkpoint_id"])
    if last:
        for entry in export_operations(site_name)[::-1]:
            if entry.get("checkpoint_id"):
                return str(entry["checkpoint_id"])
    raise click.ClickException("Provide --op-id or --last.")


@click.command(name="rollback")
@click.option("--site", "site_name", default=None)
@click.option("--op-id", default=None)
@click.option("--last", is_flag=True, default=False)
@click.option("--checkpoint-id", default=None)
@click.option("--dry-run", is_flag=True, default=False)
def rollback_command(
    site_name: str | None,
    op_id: str | None,
    last: bool,
    checkpoint_id: str | None,
    dry_run: bool,
) -> None:
    local_config, client = get_site_context(site_name)
    checkpoint_id = checkpoint_id or _resolve_checkpoint_id(local_config["site_name"], op_id, last)
    response = rollback_remote_checkpoint(client, checkpoint_id, dry_run=dry_run)
    console.print_json(data=response)

