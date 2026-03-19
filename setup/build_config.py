from __future__ import annotations

import json
import secrets
import sys
from pathlib import Path

import bcrypt

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cli.lib.config import (
    ensure_project_structure,
    get_local_config_path,
    get_output_dir,
    get_plugin_config_path,
    load_local_config,
    load_plugin_config,
    save_local_config,
    save_plugin_config,
    set_active_site,
    site_name_from_url,
    write_json,
)
from setup.build_plugin import build_plugin_zip


DEFAULT_MODULES = {
    "master_enabled": True,
    "content": True,
    "media": True,
    "database": True,
    "members": False,
    "email": False,
    "forms": False,
    "woocommerce": False,
    "cpt": False,
    "cron": False,
}

DEFAULT_DEPLOY_ORDER = ["migrations", "media", "cpt", "pages", "posts", "forms", "cron"]


def generate_token() -> str:
    return secrets.token_hex(32)


def hash_token(token: str) -> str:
    return bcrypt.hashpw(token.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def build_site_configs(
    site_url: str,
    project_path: str,
    allowed_ips: list[str] | None = None,
    allow_all_ips: bool = True,
    token: str | None = None,
    page_mode: str = "html",
    css_mode: str = "inline",
    ai_cli_command: str = "claude",
    default_status: str = "draft",
    pin: str = "123456",
) -> tuple[str, dict, dict]:
    site_name = site_name_from_url(site_url)
    token = token or generate_token()
    token_hash = hash_token(token)

    local_config = {
        "site_name": site_name,
        "site_url": site_url,
        "token": token,
        "project_path": project_path,
        "page_mode": page_mode,
        "css_mode": css_mode,
        "default_status": default_status,
        "ai_cli_command": ai_cli_command,
        "ai_operation_mode": "assisted",
        "wc_consumer_key": "",
        "wc_consumer_secret": "",
        "deploy_order": DEFAULT_DEPLOY_ORDER,
        "modules": {key: value for key, value in DEFAULT_MODULES.items() if key != "master_enabled"},
        "circuit_breaker": {
            "consecutive_failure_threshold": 3,
            "failure_window_minutes": 10,
            "partial_counts_as_failure": True,
            "human_pin_to_reset": True,
            "human_pin": pin,
            "block_reads_when_open": False,
        },
        "checkpoint": {
            "auto_checkpoint": True,
            "local_copy": True,
        },
        "reconcile": {
            "auto_before_ai": False,
        },
    }

    plugin_config = {
        "site_name": site_name,
        "site_url": site_url,
        "token_hash": token_hash,
        "allow_all_ips": allow_all_ips,
        "allowed_ips": allowed_ips or [],
        "require_https": True,
        "replay_window_seconds": 30,
        "rate_limit_per_minute": 20,
        "max_output_bytes": 524288,
        "exec_timeout_seconds": 30,
        "page_mode": page_mode,
        "css_mode": css_mode,
        "modules": DEFAULT_MODULES.copy(),
        "telemetry": {
            "capture_php_errors": True,
            "capture_memory": True,
        },
        "checkpoint": {
            "enabled": True,
        },
        "journal": {
            "enabled": True,
        },
        "log_retention_count": 500,
    }
    return site_name, local_config, plugin_config


def write_site_artifacts(site_name: str, local_config: dict, plugin_config: dict) -> dict[str, Path]:
    ensure_project_structure(local_config["project_path"])
    write_json(get_local_config_path(site_name), local_config)
    write_json(get_plugin_config_path(site_name), plugin_config)
    set_active_site(site_name)

    output_dir = get_output_dir(site_name)
    zip_path = build_plugin_zip(plugin_config, output_dir / "wp-remote-shell.zip")
    wp_config_line = "define('WRS_CONFIG_PATH', dirname(__FILE__) . '/wp-content/uploads/wrs/plugin.config.json');"
    (output_dir / "wp-config-line.txt").write_text(wp_config_line + "\n", encoding="utf-8")
    (output_dir / "plugin.config.json").write_text(
        json.dumps(plugin_config, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "output_dir": output_dir,
        "zip_path": zip_path,
        "wp_config_line": output_dir / "wp-config-line.txt",
    }


def rotate_site_token(site_name: str) -> tuple[dict, dict, str]:
    local_config = load_local_config(site_name)
    plugin_config = load_plugin_config(site_name)
    token = generate_token()
    local_config["token"] = token
    plugin_config["token_hash"] = hash_token(token)
    save_local_config(site_name, local_config)
    save_plugin_config(site_name, plugin_config)
    return local_config, plugin_config, token


def update_site_ips(site_name: str, allowed_ips: list[str], allow_all_ips: bool | None = None) -> tuple[dict, dict]:
    local_config = load_local_config(site_name)
    plugin_config = load_plugin_config(site_name)
    plugin_config["allowed_ips"] = allowed_ips
    if allow_all_ips is not None:
        plugin_config["allow_all_ips"] = allow_all_ips
    save_plugin_config(site_name, plugin_config)
    return local_config, plugin_config


def update_site_modules(site_name: str, modules: dict[str, bool]) -> tuple[dict, dict]:
    local_config = load_local_config(site_name)
    plugin_config = load_plugin_config(site_name)
    local_config["modules"].update(modules)
    plugin_config["modules"].update(modules)
    save_local_config(site_name, local_config)
    save_plugin_config(site_name, plugin_config)
    return local_config, plugin_config


def upgrade_site_config(site_name: str) -> tuple[dict, dict]:
    local_config = load_local_config(site_name)
    plugin_config = load_plugin_config(site_name)
    _, fresh_local, fresh_plugin = build_site_configs(
        site_url=local_config["site_url"],
        project_path=local_config["project_path"],
        allowed_ips=plugin_config.get("allowed_ips", []),
        allow_all_ips=plugin_config.get("allow_all_ips", False),
        token=local_config["token"],
        page_mode=local_config.get("page_mode", "html"),
        css_mode=local_config.get("css_mode", "inline"),
        ai_cli_command=local_config.get("ai_cli_command", "claude"),
        default_status=local_config.get("default_status", "draft"),
        pin=local_config.get("circuit_breaker", {}).get("human_pin", "123456"),
    )
    fresh_local.update(local_config)
    fresh_local["circuit_breaker"] = {**fresh_local["circuit_breaker"], **local_config.get("circuit_breaker", {})}
    fresh_local["checkpoint"] = {**fresh_local["checkpoint"], **local_config.get("checkpoint", {})}
    fresh_local["reconcile"] = {**fresh_local["reconcile"], **local_config.get("reconcile", {})}
    fresh_local["modules"] = {**fresh_local["modules"], **local_config.get("modules", {})}

    fresh_plugin.update(plugin_config)
    fresh_plugin["modules"] = {**fresh_plugin["modules"], **plugin_config.get("modules", {})}
    fresh_plugin["telemetry"] = {**fresh_plugin["telemetry"], **plugin_config.get("telemetry", {})}
    fresh_plugin["checkpoint"] = {**fresh_plugin["checkpoint"], **plugin_config.get("checkpoint", {})}
    fresh_plugin["journal"] = {**fresh_plugin["journal"], **plugin_config.get("journal", {})}

    save_local_config(site_name, fresh_local)
    save_plugin_config(site_name, fresh_plugin)
    return fresh_local, fresh_plugin
