from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import click
from rich.console import Console
from rich.table import Table

from cli.lib.config import get_active_site, list_sites, set_active_site
from cli.modules.checkpoint_cmd import checkpoint_group
from cli.modules.config_cmd import config_group
from cli.modules.circuit_cmd import circuit_group
from cli.modules.connect import disconnect_command, pair_command
from cli.modules.deploy import deploy_command
from cli.modules.preflight_cmd import preflight_command
from cli.modules.journal_cmd import journal_group
from cli.modules.page import page_group
from cli.modules.reconcile_cmd import reconcile_group
from cli.modules.rollback_cmd import rollback_command
from cli.modules.server import server_group
from cli.modules.setup_cmd import setup_group


console = Console()


@click.group()
def cli() -> None:
    """WP Remote Shell CLI."""


@cli.command("status")
@click.option("--site", "site_name", default=None, help="Configured site name.")
def status(site_name: str | None) -> None:
    from cli.modules.common import get_site_context

    local_config, client = get_site_context(site_name)
    response = client.request("GET", "/server/health")
    table = Table(title=f"WRS Status: {local_config['site_name']}")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("site_url", response.get("site_url", ""))
    table.add_row("plugin_version", str(response.get("plugin_version", "")))
    table.add_row("php_version", str(response.get("php_version", "")))
    table.add_row("wp_version", str(response.get("wp_version", "")))
    table.add_row("status", str(response.get("status", "")))
    console.print(table)


@cli.command("sites")
def sites() -> None:
    try:
        active = get_active_site()
    except FileNotFoundError:
        active = None
    table = Table(title="Configured WRS Sites")
    table.add_column("Site")
    table.add_column("Active")
    for site in list_sites():
        table.add_row(site, "yes" if site == active else "")
    console.print(table)


@cli.command("use")
@click.argument("site_name")
def use_site(site_name: str) -> None:
    if site_name not in list_sites():
        raise click.ClickException(f"Unknown site: {site_name}")
    set_active_site(site_name)
    console.print(f"[green]Active site set[/green] -> {site_name}")


cli.add_command(page_group)
cli.add_command(server_group)
cli.add_command(setup_group)
cli.add_command(pair_command)
cli.add_command(disconnect_command)
cli.add_command(circuit_group)
cli.add_command(deploy_command)
cli.add_command(journal_group)
cli.add_command(checkpoint_group)
cli.add_command(rollback_command)
cli.add_command(reconcile_group)
cli.add_command(config_group)
cli.add_command(preflight_command)


@cli.command("pull")
@click.option("--site", "site_name", default=None, help="Configured site name.")
@click.option("--slug", default=None)
@click.option("--all-pages", is_flag=True, default=False)
def pull(site_name: str | None, slug: str | None, all_pages: bool) -> None:
    ctx = click.get_current_context()
    if all_pages:
        from cli.modules.common import get_site_context, resolve_project_file

        local_config, client = get_site_context(site_name)
        pages = client.request("GET", "/content/page/list").get("pages", [])
        for page in pages:
            output = resolve_project_file(local_config, f"pages/{page['slug']}.html")
            ctx.invoke(page_group.commands["get"], site_name=site_name, slug=page["slug"], output=output)
        return
    if not slug:
        raise click.ClickException("Provide --slug or --all-pages.")
    ctx.invoke(page_group.commands["get"], site_name=site_name, slug=slug, output=None)


@cli.command("diff")
@click.option("--site", "site_name", default=None, help="Configured site name.")
@click.option("--slug", required=True)
@click.option("--file", "html_file", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
def diff(site_name: str | None, slug: str, html_file: Path) -> None:
    ctx = click.get_current_context()
    ctx.invoke(page_group.commands["diff"], site_name=site_name, slug=slug, html_file=html_file)


if __name__ == "__main__":
    cli()
