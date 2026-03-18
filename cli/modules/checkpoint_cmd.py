from __future__ import annotations

import json

import click
from rich.table import Table

from cli.lib.checkpoint import list_local_checkpoints, read_local_checkpoint
from cli.lib.config import get_checkpoint_dir, load_local_config
from cli.modules.common import console


@click.group(name="checkpoint")
def checkpoint_group() -> None:
    """Checkpoint inspection commands."""


@checkpoint_group.command("list")
@click.option("--site", "site_name", default=None)
def list_cmd(site_name: str | None) -> None:
    local_config = load_local_config(site_name)
    checkpoints = list_local_checkpoints(local_config["site_name"])
    table = Table(title=f"Checkpoints: {local_config['site_name']}")
    for column in ("checkpoint_id", "op_id", "op_type", "created_at"):
        table.add_column(column)
    for checkpoint in checkpoints[::-1]:
        table.add_row(
            checkpoint.get("checkpoint_id", ""),
            checkpoint.get("op_id", ""),
            checkpoint.get("op_type", ""),
            checkpoint.get("created_at", ""),
        )
    console.print(table)


@checkpoint_group.command("show")
@click.option("--site", "site_name", default=None)
@click.option("--checkpoint-id", required=True)
def show_cmd(site_name: str | None, checkpoint_id: str) -> None:
    local_config = load_local_config(site_name)
    console.print_json(data=read_local_checkpoint(local_config["site_name"], checkpoint_id))


@checkpoint_group.command("clear")
@click.option("--site", "site_name", default=None)
def clear_cmd(site_name: str | None) -> None:
    local_config = load_local_config(site_name)
    for path in get_checkpoint_dir(local_config["site_name"]).glob("*.json"):
        path.unlink(missing_ok=True)
    console.print(f"[green]Cleared[/green] local checkpoints for {local_config['site_name']}")

