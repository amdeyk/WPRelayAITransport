from __future__ import annotations

import json
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DIR = ROOT / "plugin"


def build_plugin_zip(plugin_config: dict, output_zip: Path) -> Path:
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    runtime_bytes = (json.dumps(plugin_config, indent=2, sort_keys=True) + "\n").encode("utf-8")

    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(PLUGIN_DIR.rglob("*")):
            if path.is_dir():
                continue
            relative = path.relative_to(PLUGIN_DIR).as_posix()
            archive.write(path, f"wp-remote-shell/{relative}")
        archive.writestr("wp-remote-shell/runtime/plugin.config.json", runtime_bytes)

    return output_zip

