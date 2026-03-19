from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rich.console import Console
from rich.prompt import Confirm, Prompt

from cli.lib.config import ensure_project_structure, get_active_site, load_local_config, load_plugin_config, site_name_from_url
from setup.build_config import (
    build_site_configs,
    rotate_site_token,
    update_site_ips,
    update_site_modules,
    upgrade_site_config,
    write_site_artifacts,
)


console = Console()
MODULE_NAMES = ["content", "media", "database", "members", "email", "forms", "woocommerce", "cpt", "cron"]


def ask_modules(existing: dict[str, bool] | None = None) -> dict[str, bool]:
    existing = existing or {}
    return {
        "content": True,
        "media": Confirm.ask("Enable media module?", default=existing.get("media", True)),
        "database": Confirm.ask("Enable database module?", default=existing.get("database", True)),
        "members": Confirm.ask("Enable members module?", default=existing.get("members", False)),
        "email": Confirm.ask("Enable email module?", default=existing.get("email", False)),
        "forms": Confirm.ask("Enable forms module?", default=existing.get("forms", False)),
        "woocommerce": Confirm.ask("Enable WooCommerce module?", default=existing.get("woocommerce", False)),
        "cpt": Confirm.ask("Enable CPT module?", default=existing.get("cpt", False)),
        "cron": Confirm.ask("Enable cron module?", default=existing.get("cron", False)),
    }


def resolve_site_name(site_name: str | None) -> str:
    if site_name:
        return site_name
    return get_active_site()


def interactive_new_site() -> None:
    console.print("[bold]WP Remote Shell setup[/bold]")
    site_url = Prompt.ask("WordPress site URL", default="https://example.com").strip()
    site_name = site_name_from_url(site_url)
    project_default = str((Path.home() / "wrs-sites" / site_name).resolve())
    project_path = Prompt.ask("Local project path", default=project_default).strip()
    allow_all_ips = Confirm.ask("Allow all IPs during initial setup?", default=True)
    allowed_ips = []
    if not allow_all_ips:
        allowed_ips = Prompt.ask("Allowlisted IPs (comma separated)", default="127.0.0.1").split(",")
    token = Prompt.ask("Secret token (leave blank to auto-generate)", default="", show_default=False).strip() or None
    page_mode = Prompt.ask("Page mode", choices=["html", "elementor"], default="html")
    css_mode = Prompt.ask("CSS mode", choices=["inline", "enqueue"], default="inline")
    default_status = Prompt.ask("Default page status", choices=["draft", "publish"], default="draft")
    ai_cli_command = Prompt.ask("AI CLI command", default="claude")
    pin = Prompt.ask("Circuit breaker reset PIN", default="123456")
    modules = ask_modules()

    site_name, local_config, plugin_config = build_site_configs(
        site_url=site_url,
        project_path=project_path,
        allowed_ips=[item.strip() for item in allowed_ips if item.strip()],
        allow_all_ips=allow_all_ips,
        token=token,
        page_mode=page_mode,
        css_mode=css_mode,
        ai_cli_command=ai_cli_command,
        default_status=default_status,
        pin=pin,
    )
    local_config["modules"] = modules
    plugin_config["modules"].update(modules)

    ensure_project_structure(project_path)
    paths = write_site_artifacts(site_name, local_config, plugin_config)
    console.print(f"[green]Site configured:[/green] {site_name}")
    console.print(f"Project path: {project_path}")
    console.print(f"Plugin ZIP: {paths['zip_path']}")
    console.print(f"wp-config line: {paths['wp_config_line']}")


def rotate_token_flow(site_name: str) -> None:
    local_config, plugin_config, token = rotate_site_token(site_name)
    paths = write_site_artifacts(site_name, local_config, plugin_config)
    console.print(f"[green]Token rotated[/green] for {site_name}")
    console.print(f"New token: {token}")
    console.print(f"Plugin ZIP: {paths['zip_path']}")


def update_ips_flow(site_name: str) -> None:
    current = load_local_config(site_name)
    plugin_current = load_plugin_config(site_name)
    allow_all_ips = Confirm.ask(
        "Allow all IPs during setup?",
        default=plugin_current.get("allow_all_ips", False),
    )
    allowed_ips = []
    if not allow_all_ips:
        allowed_ips = Prompt.ask(
            "Allowlisted IPs (comma separated)",
            default=",".join(plugin_current.get("allowed_ips", ["127.0.0.1"])) or "127.0.0.1",
        ).split(",")
    _, plugin_config = update_site_ips(
        site_name,
        [item.strip() for item in allowed_ips if item.strip()],
        allow_all_ips=allow_all_ips,
    )
    paths = write_site_artifacts(site_name, current, plugin_config)
    console.print(f"[green]Allowlist updated[/green] for {site_name}")
    console.print(f"Plugin ZIP: {paths['zip_path']}")


def update_modules_flow(site_name: str) -> None:
    current = load_local_config(site_name)
    modules = ask_modules(current.get("modules", {}))
    local_config, plugin_config = update_site_modules(site_name, modules)
    paths = write_site_artifacts(site_name, local_config, plugin_config)
    console.print(f"[green]Modules updated[/green] for {site_name}")
    console.print(f"Plugin ZIP: {paths['zip_path']}")


def upgrade_flow(site_name: str) -> None:
    local_config, plugin_config = upgrade_site_config(site_name)
    paths = write_site_artifacts(site_name, local_config, plugin_config)
    console.print(f"[green]Config upgraded[/green] for {site_name}")
    console.print(f"Plugin ZIP: {paths['zip_path']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="WP Remote Shell interactive setup wizard.")
    parser.add_argument("--site", default=None, help="Existing configured site name.")
    parser.add_argument("--rotate-token", action="store_true", help="Rotate the secret token for a site.")
    parser.add_argument("--only", choices=["ips", "modules"], default=None, help="Update only part of the config.")
    parser.add_argument("--upgrade", action="store_true", help="Upgrade an existing site config to the latest schema.")
    parser.add_argument("--new-site", action="store_true", help="Force the new-site flow.")
    args = parser.parse_args()

    if args.rotate_token:
        rotate_token_flow(resolve_site_name(args.site))
        return
    if args.only == "ips":
        update_ips_flow(resolve_site_name(args.site))
        return
    if args.only == "modules":
        update_modules_flow(resolve_site_name(args.site))
        return
    if args.upgrade:
        upgrade_flow(resolve_site_name(args.site))
        return

    interactive_new_site()


if __name__ == "__main__":
    main()
