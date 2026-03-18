from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from setup.build_config import build_site_configs, write_site_artifacts


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate WRS config files.")
    parser.add_argument("--site-url", required=True)
    parser.add_argument("--project-path", required=True)
    parser.add_argument("--allowed-ip", action="append", dest="allowed_ips", required=True)
    parser.add_argument("--token", default=None)
    args = parser.parse_args()

    site_name, local_config, plugin_config = build_site_configs(
        site_url=args.site_url,
        project_path=args.project_path,
        allowed_ips=args.allowed_ips,
        token=args.token,
    )
    paths = write_site_artifacts(site_name, local_config, plugin_config)
    print(json.dumps({key: str(value) for key, value in paths.items()}, indent=2))


if __name__ == "__main__":
    main()
