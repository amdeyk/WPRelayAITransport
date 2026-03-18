from __future__ import annotations

import click
from rich.table import Table

from cli.modules.common import console, get_site_context


@click.group(name="server")
def server_group() -> None:
    """Server utilities."""


@server_group.command("health")
@click.option("--site", "site_name", default=None, help="Configured site name.")
def health(site_name: str | None) -> None:
    local_config, client = get_site_context(site_name)
    response = client.request("GET", "/server/health")
    table = Table(title=f"WRS Server Health: {local_config['site_name']}")
    table.add_column("Field")
    table.add_column("Value")
    for key in ("site_url", "plugin_version", "php_version", "wp_version", "status"):
        table.add_row(key, str(response.get(key, "")))
    console.print(table)


def _print_response_table(title: str, payload: dict) -> None:
    table = Table(title=title)
    table.add_column("Field")
    table.add_column("Value")
    for key, value in payload.items():
        table.add_row(str(key), str(value))
    console.print(table)


@server_group.command("errors")
@click.option("--site", "site_name", default=None, help="Configured site name.")
def errors(site_name: str | None) -> None:
    local_config, client = get_site_context(site_name)
    response = client.request("GET", "/server/errors")
    _print_response_table(f"WRS Server Errors: {local_config['site_name']}", response)


@server_group.command("db-status")
@click.option("--site", "site_name", default=None, help="Configured site name.")
def db_status(site_name: str | None) -> None:
    local_config, client = get_site_context(site_name)
    response = client.request("GET", "/server/db-status")
    _print_response_table(f"WRS DB Status: {local_config['site_name']}", response)


@server_group.command("file-check")
@click.option("--site", "site_name", default=None, help="Configured site name.")
def file_check(site_name: str | None) -> None:
    local_config, client = get_site_context(site_name)
    response = client.request("GET", "/server/file-check")
    _print_response_table(f"WRS File Check: {local_config['site_name']}", response)


@server_group.command("php-info")
@click.option("--site", "site_name", default=None, help="Configured site name.")
def php_info(site_name: str | None) -> None:
    local_config, client = get_site_context(site_name)
    response = client.request("GET", "/server/php-info")
    _print_response_table(f"WRS PHP Info: {local_config['site_name']}", response)
