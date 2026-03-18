from __future__ import annotations

from pathlib import Path

import click
from rich.table import Table

from cli.lib.config import load_local_config
from cli.lib.reconcile import reconcile_pages
from cli.modules.common import console, get_site_context


@click.group(name="reconcile", invoke_without_command=True)
@click.option("--all", "all_flag", is_flag=True, default=False)
@click.pass_context
def reconcile_group(ctx: click.Context, all_flag: bool) -> None:
    """Reconciliation commands."""
    if ctx.invoked_subcommand is None and all_flag:
        ctx.invoke(pages_cmd, site_name=None)
        ctx.invoke(journal_cmd, site_name=None)


@reconcile_group.command("pages")
@click.option("--site", "site_name", default=None)
def pages_cmd(site_name: str | None) -> None:
    local_config, client = get_site_context(site_name)
    response = client.request("GET", "/content/page/list")
    results = reconcile_pages(Path(local_config["project_path"]).expanduser(), response.get("pages", []))
    table = Table(title=f"Reconcile Pages: {local_config['site_name']}")
    table.add_column("slug")
    table.add_column("state")
    for result in results:
        table.add_row(result["slug"], result["state"])
    console.print(table)


@reconcile_group.command("journal")
@click.option("--site", "site_name", default=None)
def journal_cmd(site_name: str | None) -> None:
    local_config = load_local_config(site_name)
    console.print(f"Local journal path: {local_config['site_name']}")
    console.print("Journal reconciliation is currently local-only; compare op_ids before replaying writes.")
