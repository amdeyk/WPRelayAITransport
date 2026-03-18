from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

from cli.lib.circuit import load_state, reset
from cli.lib.config import load_local_config
from cli.modules.common import get_site_context


console = Console()


@click.group(name="circuit-breaker")
def circuit_group() -> None:
    """Circuit breaker commands."""


@circuit_group.command("status")
@click.option("--site", "site_name", default=None, help="Configured site name.")
def status(site_name: str | None) -> None:
    local_config = load_local_config(site_name)
    state = load_state(local_config["site_name"])
    table = Table(title=f"Circuit Breaker: {local_config['site_name']}")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("state", state["state"])
    table.add_row("consecutive_failures", str(state["consecutive_failures"]))
    table.add_row("last_success_at", str(state["last_success_at"]))
    table.add_row("last_failure_at", str(state["last_failure_at"]))
    console.print(table)


@circuit_group.command("reset")
@click.option("--site", "site_name", default=None, help="Configured site name.")
@click.option("--pin", prompt=True, hide_input=True)
def reset_cmd(site_name: str | None, pin: str) -> None:
    local_config = load_local_config(site_name)
    state = reset(local_config["site_name"], local_config, pin)
    console.print(f"[green]Circuit reset[/green] for {local_config['site_name']} -> {state['state']}")


@circuit_group.command("history")
@click.option("--site", "site_name", default=None, help="Configured site name.")
def history(site_name: str | None) -> None:
    local_config = load_local_config(site_name)
    state = load_state(local_config["site_name"])
    table = Table(title=f"Circuit History: {local_config['site_name']}")
    table.add_column("time")
    table.add_column("status")
    table.add_column("detail")
    for item in state.get("history", [])[-10:][::-1]:
        table.add_row(item.get("time", ""), item.get("status", ""), str(item.get("detail", "")))
    console.print(table)


@circuit_group.command("test")
@click.option("--site", "site_name", default=None, help="Configured site name.")
def test(site_name: str | None) -> None:
    local_config, client = get_site_context(site_name)
    response = client.request("GET", "/server/health")
    console.print(f"[green]Health OK[/green] {local_config['site_name']} -> {response.get('status')}")
