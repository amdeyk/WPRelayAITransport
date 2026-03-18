from __future__ import annotations

import click
from rich.table import Table

from cli.lib.config import load_local_config, load_plugin_config
from cli.modules.common import console


@click.group(name="config")
def config_group() -> None:
    """Config helpers."""


@config_group.command("check")
@click.option("--site", "site_name", default=None)
def check(site_name: str | None) -> None:
    local_config = load_local_config(site_name)
    plugin_config = load_plugin_config(site_name)
    table = Table(title=f"Config Check: {local_config['site_name']}")
    table.add_column("Check")
    table.add_column("Result")
    table.add_row("site_url", "ok" if local_config.get("site_url") == plugin_config.get("site_url") else "mismatch")
    table.add_row("page_mode", "ok" if local_config.get("page_mode") == plugin_config.get("page_mode") else "mismatch")
    table.add_row("css_mode", "ok" if local_config.get("css_mode") == plugin_config.get("css_mode") else "mismatch")
    table.add_row("token_hash_present", "yes" if plugin_config.get("token_hash") else "no")
    table.add_row("allowed_ips", ", ".join(plugin_config.get("allowed_ips", [])))
    console.print(table)

