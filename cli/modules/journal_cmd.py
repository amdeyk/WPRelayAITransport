from __future__ import annotations

import json
from pathlib import Path

import click
from rich.table import Table

from cli.lib.config import load_local_config
from cli.lib.journal import export_operations, get_operation, read_records
from cli.modules.common import console


@click.group(name="journal")
def journal_group() -> None:
    """Local journal inspection commands."""


@journal_group.command("list")
@click.option("--site", "site_name", default=None)
@click.option("--limit", default=10, show_default=True)
def list_cmd(site_name: str | None, limit: int) -> None:
    local_config = load_local_config(site_name)
    entries = export_operations(local_config["site_name"])[-limit:][::-1]
    table = Table(title=f"Journal: {local_config['site_name']}")
    for column in ("op_id", "op_type", "status", "operator", "event_time", "checkpoint_id"):
        table.add_column(column)
    for entry in entries:
        table.add_row(
            entry.get("op_id", ""),
            entry.get("op_type", ""),
            entry.get("status", ""),
            entry.get("operator", ""),
            entry.get("event_time", ""),
            str(entry.get("checkpoint_id", "")),
        )
    console.print(table)


@journal_group.command("show")
@click.option("--site", "site_name", default=None)
@click.option("--op-id", required=True)
def show_cmd(site_name: str | None, op_id: str) -> None:
    local_config = load_local_config(site_name)
    entry = get_operation(local_config["site_name"], op_id)
    if not entry:
        raise click.ClickException(f"Unknown op_id: {op_id}")
    console.print_json(data=entry)


@journal_group.command("tail")
@click.option("--site", "site_name", default=None)
@click.option("--limit", default=20, show_default=True)
def tail_cmd(site_name: str | None, limit: int) -> None:
    local_config = load_local_config(site_name)
    for record in read_records(local_config["site_name"])[-limit:]:
        console.print_json(data=record)


@journal_group.command("export")
@click.option("--site", "site_name", default=None)
@click.option("--output", required=True, type=click.Path(dir_okay=False, path_type=Path))
def export_cmd(site_name: str | None, output: Path) -> None:
    local_config = load_local_config(site_name)
    output.write_text(json.dumps(export_operations(local_config["site_name"]), indent=2), encoding="utf-8")
    console.print(f"[green]Exported[/green] {output}")

