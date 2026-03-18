from __future__ import annotations

import click
from rich.console import Console

from cli.lib.config import load_local_config, load_plugin_config
from cli.lib.http import WrsClient


console = Console()


@click.group(name="setup")
def setup_group() -> None:
    """Setup helpers."""


@setup_group.command("deploy-config")
@click.option("--site", "site_name", default=None, help="Configured site name.")
def deploy_config(site_name: str | None) -> None:
    local_config = load_local_config(site_name)
    plugin_config = load_plugin_config(site_name)
    client = WrsClient(local_config)
    response = client.request("POST", "/setup/config", payload={"config": plugin_config})
    console.print(f"[green]Config deployed[/green] to {local_config['site_url']}")
    console.print(response.get("message", ""))

