from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from setup.build_plugin import build_plugin_zip


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the WRS plugin ZIP.")
    parser.add_argument("--config", required=True, help="Path to plugin.config.json")
    parser.add_argument("--output", required=True, help="Destination zip file")
    args = parser.parse_args()

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    build_plugin_zip(config, Path(args.output))


if __name__ == "__main__":
    main()
