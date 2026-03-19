from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path
from urllib.parse import urlparse, urlunparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table

from cli.lib.config import (
    ensure_project_structure,
    get_active_site,
    load_local_config,
    load_plugin_config,
    site_exists,
    site_name_from_url,
)
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
MODULE_DESCRIPTIONS = {
    "content": "Pages and page-related content commands.",
    "media": "Not implemented end-to-end yet. Leave off unless you are developing it.",
    "database": "Not implemented end-to-end yet. Leave off unless you are developing it.",
    "members": "Not implemented end-to-end yet. Leave off unless you are developing it.",
    "email": "Not implemented end-to-end yet. Leave off unless you are developing it.",
    "forms": "Not implemented end-to-end yet. Leave off unless you are developing it.",
    "woocommerce": "Not implemented end-to-end yet. Leave off unless you are developing it.",
    "cpt": "Not implemented end-to-end yet. Leave off unless you are developing it.",
    "cron": "Not implemented end-to-end yet. Leave off unless you are developing it.",
}
SAFE_MODULE_DEFAULTS = {name: (name == "content") for name in MODULE_NAMES}

_TOTAL_STEPS = 8


def _step_rule(step: int, title: str) -> None:
    console.rule(f"[bold cyan]Step {step}/{_TOTAL_STEPS}[/bold cyan] — {title}")


def _print_choice_table(title: str, rows: list[tuple[str, str, str]]) -> None:
    table = Table(title=title)
    table.add_column("Option", style="cyan")
    table.add_column("When To Use It")
    table.add_column("Default")
    for option, description, default in rows:
        table.add_row(option, description, default)
    console.print(table)


def _prompt_non_empty(message: str, default: str | None = None) -> str:
    while True:
        value = Prompt.ask(message, default=default).strip()
        if value:
            return value
        console.print("[red]A value is required.[/red]")


def _normalize_site_url(value: str) -> str:
    candidate = value.strip()
    if "://" not in candidate:
        candidate = f"https://{candidate}"
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Enter a full site URL such as https://example.com.")
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path.rstrip("/"), "", "", ""))


def _ask_site_url() -> str:
    while True:
        try:
            site_url = _normalize_site_url(_prompt_non_empty("WordPress site URL", default="https://example.com"))
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
            continue
        console.print(f"Site folder name: [bold]{site_name_from_url(site_url)}[/bold]")
        return site_url


def _ask_project_path(default_path: str) -> str:
    project_path = _prompt_non_empty("Local project path", default=default_path)
    return str(Path(project_path).expanduser().resolve())


def _ask_allowed_ips() -> tuple[bool, list[str]]:
    console.print("Start open if you want the fastest first connection, then tighten the allowlist after verification.")
    allow_all_ips = Confirm.ask("Allow any IP during the initial setup?", default=True)
    if allow_all_ips:
        return True, []
    while True:
        raw_ips = _prompt_non_empty("Allowlisted IPs (comma separated)", default="127.0.0.1")
        allowed_ips = [item.strip() for item in raw_ips.split(",") if item.strip()]
        if allowed_ips:
            return False, allowed_ips
        console.print("[red]Enter at least one IP if open access is disabled.[/red]")


def _ask_token() -> tuple[str | None, str]:
    console.print("WRS can generate a strong token for you. Manual entry is only needed if you already manage secrets elsewhere.")
    auto_generate = Confirm.ask("Auto-generate the secret token?", default=True)
    if auto_generate:
        return None, "auto-generated"
    while True:
        token = Prompt.ask("Secret token", password=True).strip()
        if len(token) >= 16:
            return token, "manual"
        console.print("[red]Use at least 16 characters for a manual token.[/red]")


def _ask_pin(existing_default: str = "123456") -> str:
    console.print("This PIN is required to reset the circuit breaker after repeated failures.")
    while True:
        pin = Prompt.ask("Circuit breaker reset PIN", default=existing_default, password=True).strip()
        if not (pin.isdigit() and len(pin) >= 6):
            console.print("[red]Use digits only and at least 6 characters.[/red]")
            continue
        confirm_pin = Prompt.ask("Confirm PIN", password=True).strip()
        if pin != confirm_pin:
            console.print("[red]PIN values did not match.[/red]")
            continue
        return pin


def _ask_optional_ai_command(default: str = "") -> str:
    console.print("Optional. Leave blank if you do not want to enable `page generate` or `page ai-update` yet.")
    while True:
        ai_cli_command = Prompt.ask("AI CLI command", default=default, show_default=bool(default)).strip()
        if not ai_cli_command:
            return ""
        executable = ai_cli_command.split()[0].strip("\"'")
        if shutil.which(executable) or Path(executable).expanduser().exists():
            return ai_cli_command
        console.print("[yellow]That command was not found on PATH. WRS can still save it if you plan to install it later.[/yellow]")
        if Confirm.ask("Keep this AI command anyway?", default=True):
            return ai_cli_command


def _ask_runtime_defaults() -> tuple[str, str, str]:
    _print_choice_table(
        "Page Mode",
        [
            ("html", "Recommended. WRS manages raw HTML directly.", "yes"),
            ("elementor", "Use only if this site is intentionally Elementor-based.", "no"),
        ],
    )
    page_mode = Prompt.ask("Page mode", choices=["html", "elementor"], default="html")

    _print_choice_table(
        "CSS Mode",
        [
            ("inline", "Recommended. Simplest setup and easiest to debug.", "yes"),
            ("enqueue", "Separate CSS asset written on the server.", "no"),
        ],
    )
    css_mode = Prompt.ask("CSS mode", choices=["inline", "enqueue"], default="inline")

    _print_choice_table(
        "Default Page Status",
        [
            ("draft", "Recommended. Review before publishing.", "yes"),
            ("publish", "Use only when immediate live deployment is intended.", "no"),
        ],
    )
    default_status = Prompt.ask("Default page status", choices=["draft", "publish"], default="draft")
    return page_mode, css_mode, default_status


def _print_module_table(existing: dict[str, bool]) -> None:
    table = Table(title="Modules")
    table.add_column("Module", style="cyan")
    table.add_column("Description")
    table.add_column("Default")
    for name in MODULE_NAMES:
        default_label = "on" if existing.get(name, SAFE_MODULE_DEFAULTS[name]) else "off"
        table.add_row(name, MODULE_DESCRIPTIONS[name], default_label)
    console.print(table)


def ask_modules(existing: dict[str, bool] | None = None, *, offer_safe_profile: bool = False) -> dict[str, bool]:
    existing = existing or {}
    _print_module_table(existing)
    if offer_safe_profile and Confirm.ask("Use the safe recommended module set (`content` only)?", default=True):
        return SAFE_MODULE_DEFAULTS.copy()
    return {
        "content": True,
        "media": Confirm.ask("Enable media module?", default=existing.get("media", False)),
        "database": Confirm.ask("Enable database module?", default=existing.get("database", False)),
        "members": Confirm.ask("Enable members module?", default=existing.get("members", False)),
        "email": Confirm.ask("Enable email module?", default=existing.get("email", False)),
        "forms": Confirm.ask("Enable forms module?", default=existing.get("forms", False)),
        "woocommerce": Confirm.ask("Enable WooCommerce module?", default=existing.get("woocommerce", False)),
        "cpt": Confirm.ask("Enable CPT module?", default=existing.get("cpt", False)),
        "cron": Confirm.ask("Enable cron module?", default=existing.get("cron", False)),
    }


def _print_review(
    *,
    site_name: str,
    site_url: str,
    project_path: str,
    allow_all_ips: bool,
    allowed_ips: list[str],
    token_mode: str,
    page_mode: str,
    css_mode: str,
    default_status: str,
    ai_cli_command: str,
    modules: dict[str, bool],
) -> None:
    table = Table(title="Review")
    table.add_column("Setting", style="cyan")
    table.add_column("Value")
    table.add_row("site_url", site_url)
    table.add_row("site_name", site_name)
    table.add_row("project_path", project_path)
    table.add_row("access", "allow all IPs" if allow_all_ips else ", ".join(allowed_ips))
    table.add_row("token", token_mode)
    table.add_row("page_mode", page_mode)
    table.add_row("css_mode", css_mode)
    table.add_row("default_status", default_status)
    table.add_row("ai_cli_command", ai_cli_command or "disabled")
    table.add_row("modules", ", ".join(name for name, enabled in modules.items() if enabled) or "none")
    console.print(table)


def resolve_site_name(site_name: str | None) -> str:
    if site_name:
        return site_name
    return get_active_site()


def interactive_new_site() -> None:
    console.print()
    console.rule("[bold]WP Remote Shell — New Site Setup[/bold]")
    console.print(
        f"Answer each prompt. Defaults are shown in [brackets] — press Enter to accept.\n"
        f"This wizard has [bold]{_TOTAL_STEPS} steps[/bold] and will create your local config, plugin config, and plugin ZIP."
    )
    console.print()

    # ── Step 1: Site URL ──────────────────────────────────────────────────────
    _step_rule(1, "Site URL")
    site_url = _ask_site_url()
    site_name = site_name_from_url(site_url)
    project_default = str((Path.home() / "wrs-sites" / site_name).resolve())
    if site_exists(site_name):
        console.print(f"[yellow]A site config already exists for {site_name}.[/yellow]")
        if not Confirm.ask("Overwrite the existing site config and rebuild the plugin ZIP?", default=False):
            console.print("[yellow]Setup cancelled.[/yellow]")
            return
        current = load_local_config(site_name)
        project_default = current.get("project_path", project_default)

    # ── Step 2: Project path ──────────────────────────────────────────────────
    _step_rule(2, "Project")
    console.print(f"Local folder where HTML, CSS, and content files for [bold]{site_name}[/bold] will live.")
    project_path = _ask_project_path(project_default)

    # ── Step 3: Access ────────────────────────────────────────────────────────
    _step_rule(3, "Access")
    allow_all_ips, allowed_ips = _ask_allowed_ips()

    # ── Step 4: Authentication ────────────────────────────────────────────────
    _step_rule(4, "Authentication")
    token, token_mode = _ask_token()

    # ── Step 5: Safety (PIN) — kept next to auth since both are security config
    _step_rule(5, "Safety")
    pin = _ask_pin()

    # ── Step 6: Content defaults ──────────────────────────────────────────────
    _step_rule(6, "Content Defaults")
    page_mode, css_mode, default_status = _ask_runtime_defaults()

    # ── Step 7: AI ────────────────────────────────────────────────────────────
    _step_rule(7, "AI")
    ai_cli_command = _ask_optional_ai_command()

    # ── Step 8: Modules ───────────────────────────────────────────────────────
    _step_rule(8, "Modules")
    console.print("Only [bold]content[/bold] is implemented end-to-end. Enable others only if you are actively developing them.")
    modules = ask_modules(offer_safe_profile=True)

    # ── Review ────────────────────────────────────────────────────────────────
    console.rule("Review — check before writing")
    _print_review(
        site_name=site_name,
        site_url=site_url,
        project_path=project_path,
        allow_all_ips=allow_all_ips,
        allowed_ips=allowed_ips,
        token_mode=token_mode,
        page_mode=page_mode,
        css_mode=css_mode,
        default_status=default_status,
        ai_cli_command=ai_cli_command,
        modules=modules,
    )
    if not Confirm.ask("Write the config files and build the plugin ZIP?", default=True):
        console.print("[yellow]Setup cancelled before any files were written.[/yellow]")
        return

    # ── Write ─────────────────────────────────────────────────────────────────
    site_name, local_config, plugin_config = build_site_configs(
        site_url=site_url,
        project_path=project_path,
        allowed_ips=allowed_ips,
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

    # ── Done ──────────────────────────────────────────────────────────────────
    console.rule("[green]Setup complete[/green]")
    console.print(f"[bold]Site:[/bold]    {site_name}")
    console.print(f"[bold]Project:[/bold] {project_path}")
    console.print()
    console.print("[bold]Next steps:[/bold]")
    console.print(f"  [cyan]1.[/cyan] Upload the plugin ZIP to your WordPress site:")
    console.print(f"       {paths['zip_path']}")
    console.print(f"  [cyan]2.[/cyan] In WordPress admin: Plugins → Add New → Upload Plugin → Install → Activate")
    wp_line = paths["wp_config_line"].read_text(encoding="utf-8").strip()
    console.print(f"  [cyan]3.[/cyan] Add this line to [bold]wp-config.php[/bold] (before the 'stop editing' comment):")
    console.print(f"       [dim]{wp_line}[/dim]")
    console.print(f"  [cyan]4.[/cyan] Verify the connection:")
    console.print(f"       [bold]python cli/wrs.py status[/bold]")
    console.print()


def rotate_token_flow(site_name: str) -> None:
    local_config, plugin_config, token = rotate_site_token(site_name)
    paths = write_site_artifacts(site_name, local_config, plugin_config)
    console.print(f"[green]Token rotated[/green] for {site_name}")
    console.print(f"New token: {token}")
    console.print(f"Plugin ZIP: {paths['zip_path']}")


def update_ips_flow(site_name: str) -> None:
    current = load_local_config(site_name)
    plugin_current = load_plugin_config(site_name)
    console.rule("Access")
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
    modules = ask_modules(current.get("modules", {}), offer_safe_profile=False)
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
