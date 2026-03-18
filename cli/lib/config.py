from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


WRS_HOME = Path.home() / ".wrs"
SITES_DIR = WRS_HOME / "sites"
ACTIVE_SITE_FILE = WRS_HOME / "active-site.txt"

PROJECT_FOLDERS = [
    "pages",
    "pages-css",
    "partials",
    "posts",
    "cpt",
    "entries",
    "forms",
    "emails",
    "tiers",
    "products",
    "coupons",
    "gateways",
    "migrations",
    "seeds",
    "media",
    "menus",
    "cron",
]


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def site_name_from_url(site_url: str) -> str:
    parsed = urlparse(site_url)
    host = parsed.netloc or parsed.path
    return host.lower().replace(":", "-")


def get_site_dir(site_name: str) -> Path:
    return ensure_dir(SITES_DIR / site_name)


def get_output_dir(site_name: str) -> Path:
    return ensure_dir(Path("setup") / "output" / site_name)


def get_local_config_path(site_name: str) -> Path:
    return get_site_dir(site_name) / "local.config.json"


def get_plugin_config_path(site_name: str) -> Path:
    return get_site_dir(site_name) / "plugin.config.json"


def get_journal_path(site_name: str) -> Path:
    return get_site_dir(site_name) / "journal.ndjson"


def get_circuit_path(site_name: str) -> Path:
    return get_site_dir(site_name) / "circuit.json"


def get_checkpoint_dir(site_name: str) -> Path:
    return ensure_dir(get_site_dir(site_name) / "checkpoints")


def get_manifest_path(local_config: dict[str, Any]) -> Path:
    return Path(os.path.expanduser(local_config["project_path"])) / "wrs-manifest.json"


def site_exists(site_name: str) -> bool:
    return get_local_config_path(site_name).exists()


def list_sites() -> list[str]:
    ensure_dir(SITES_DIR)
    sites: list[str] = []
    for child in sorted(SITES_DIR.iterdir()):
        if child.is_dir() and (child / "local.config.json").exists():
            sites.append(child.name)
    return sites


def set_active_site(site_name: str) -> None:
    ensure_dir(WRS_HOME)
    ACTIVE_SITE_FILE.write_text(site_name, encoding="utf-8")


def get_active_site() -> str:
    if ACTIVE_SITE_FILE.exists():
        value = ACTIVE_SITE_FILE.read_text(encoding="utf-8").strip()
        if value:
            return value
    sites = list_sites()
    if not sites:
        raise FileNotFoundError("No WRS sites have been configured yet.")
    return sites[0]


def load_local_config(site_name: str | None = None) -> dict[str, Any]:
    site_name = site_name or get_active_site()
    config = read_json(get_local_config_path(site_name))
    config["site_name"] = site_name
    return config


def load_plugin_config(site_name: str | None = None) -> dict[str, Any]:
    site_name = site_name or get_active_site()
    config = read_json(get_plugin_config_path(site_name))
    config["site_name"] = site_name
    return config


def save_local_config(site_name: str, config: dict[str, Any]) -> None:
    write_json(get_local_config_path(site_name), config)


def save_plugin_config(site_name: str, config: dict[str, Any]) -> None:
    write_json(get_plugin_config_path(site_name), config)


def ensure_project_structure(project_path: str) -> Path:
    root = ensure_dir(Path(os.path.expanduser(project_path)))
    for folder in PROJECT_FOLDERS:
        ensure_dir(root / folder)
    ignore_path = root / ".gitignore"
    if not ignore_path.exists():
        ignore_path.write_text("media/\nwrs-manifest.json\n", encoding="utf-8")
    return root
