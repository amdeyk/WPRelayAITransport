from __future__ import annotations

import sys
from pathlib import Path

import click
import requests
from rich.console import Console
from rich.table import Table

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cli.lib.circuit import can_execute
from cli.lib.config import load_local_config
from cli.lib.http import COMMON_JSON_HEADERS, WrsClient, WrsHttpError

console = Console()

_PASS = "PASS"
_FAIL = "FAIL"
_WARN = "WARN"
_SKIP = "SKIP"


def _run(label: str, fn) -> tuple[str, str, str]:
    try:
        detail = fn() or ""
        return (label, _PASS, detail)
    except WrsHttpError as exc:
        return (label, _FAIL, str(exc))
    except Exception as exc:
        return (label, _FAIL, str(exc))


def _print_results(results: list[tuple[str, str, str]]) -> None:
    table = Table(title="WRS Preflight Checks", show_lines=False)
    table.add_column("Check", style="bold")
    table.add_column("Status", min_width=6)
    table.add_column("Detail")
    styles = {_PASS: "green", _FAIL: "red", _WARN: "yellow", _SKIP: "dim"}
    for label, status, detail in results:
        st = styles.get(status, "")
        table.add_row(label, f"[{st}]{status}[/{st}]", detail)
    console.print(table)

    failures = [r for r in results if r[1] == _FAIL]
    warns = [r for r in results if r[1] == _WARN]
    passes = [r for r in results if r[1] == _PASS]

    if failures:
        console.print(f"[red]{len(failures)} check(s) failed.[/red] Fix the issues above before operating.")
    elif warns:
        console.print(f"[yellow]{len(warns)} warning(s).[/yellow] {len(passes)} check(s) passed.")
    else:
        console.print(f"[green]All {len(passes)} checks passed.[/green] Ready to operate.")


@click.command("preflight")
@click.option("--site", "site_name", default=None, help="Site to check (default: active site).")
def preflight_command(site_name: str | None) -> None:
    """Run end-to-end connectivity and configuration checks before operating.

    Verifies: local config, site reachability, plugin auth, server config file,
    circuit breaker state, and content module availability.

    Exit code is 0 if all checks pass or only warnings, 1 if any check fails.
    """
    results: list[tuple[str, str, str]] = []
    local_config: dict | None = None
    client: WrsClient | None = None

    # ── 1. Local config ───────────────────────────────────────────────────────
    try:
        local_config = load_local_config(site_name)
        resolved_name = local_config.get("site_name", site_name or "?")
        site_url = local_config.get("site_url", "").rstrip("/")
        missing = [k for k in ("site_name", "site_url", "token") if not local_config.get(k)]
        if missing:
            results.append(("Local config", _FAIL, f"Missing required fields: {', '.join(missing)}"))
        else:
            results.append(("Local config", _PASS, f"{site_url}"))
    except Exception as exc:
        results.append(("Local config", _FAIL, str(exc)))
        _print_results(results)
        raise SystemExit(1)

    client = WrsClient(local_config)

    # ── 2. Site reachability (unauthenticated) ────────────────────────────────
    def check_reachable() -> str:
        resp = requests.get(site_url, timeout=10, allow_redirects=True, headers=COMMON_JSON_HEADERS)
        return f"HTTP {resp.status_code}"

    results.append(_run("Site reachable", check_reachable))
    site_ok = results[-1][1] == _PASS

    # ── 3. Plugin ping (authenticated — proves token + HMAC work) ─────────────
    def check_ping() -> str:
        data = client.request("GET", "/server/ping")
        return f"plugin v{data.get('plugin_version', '?')}  wp v{data.get('wp_version', '?')}"

    results.append(_run("Plugin ping (auth)", check_ping))
    ping_ok = results[-1][1] == _PASS

    # ── 4. Full server health ─────────────────────────────────────────────────
    if ping_ok:
        def check_health() -> str:
            data = client.request("GET", "/server/health")
            n_managed = len(data.get("site_inventory", {}).get("pages", []))
            return f"status={data.get('status', '?')}  managed_pages={n_managed}"
        results.append(_run("Server health", check_health))
    else:
        results.append(("Server health", _SKIP, "Skipped — plugin ping failed"))

    # ── 5. Server config file present ────────────────────────────────────────
    if ping_ok:
        def check_config_file() -> str:
            data = client.request("GET", "/server/file-check")
            if not data.get("config_exists"):
                raise RuntimeError(
                    f"Config file not found at {data.get('config_path', '?')}. "
                    "Run: python cli/wrs.py setup deploy-config"
                )
            return data.get("config_path", "present")
        results.append(_run("Server config file", check_config_file))
    else:
        results.append(("Server config file", _SKIP, "Skipped — plugin ping failed"))

    # ── 6. Circuit breaker state ──────────────────────────────────────────────
    try:
        allowed, reason = can_execute(resolved_name, local_config, write_operation=True)
        if not allowed:
            results.append(("Circuit breaker", _FAIL, reason or "OPEN — writes are blocked"))
        else:
            results.append(("Circuit breaker", _PASS, "CLOSED — writes are allowed"))
    except Exception as exc:
        results.append(("Circuit breaker", _WARN, f"Could not read state: {exc}"))

    # ── 7. Content module enabled ─────────────────────────────────────────────
    if ping_ok:
        def check_content_module() -> str:
            data = client.request("GET", "/server/ping")
            modules = data.get("modules", {})
            if not modules.get("master_enabled", True):
                raise RuntimeError("Master switch is disabled in plugin config")
            if not modules.get("content", False):
                raise RuntimeError("content module is disabled — enable it in WP Remote Shell → Settings")
            return "enabled"
        results.append(_run("Content module", check_content_module))
    else:
        results.append(("Content module", _SKIP, "Skipped — plugin ping failed"))

    # ── 8. PHP environment (informational) ───────────────────────────────────
    if ping_ok:
        def check_php() -> str:
            data = client.request("GET", "/server/php-info")
            return (
                f"php {data.get('php_version', '?')}  "
                f"memory={data.get('memory_limit', '?')}  "
                f"max_exec={data.get('max_execution_time', '?')}s"
            )
        results.append(_run("PHP environment", check_php))
    else:
        results.append(("PHP environment", _SKIP, "Skipped — plugin ping failed"))

    _print_results(results)

    if any(r[1] == _FAIL for r in results):
        raise SystemExit(1)
