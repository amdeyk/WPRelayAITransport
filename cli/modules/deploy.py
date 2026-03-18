from __future__ import annotations

import json
from pathlib import Path

import click

from cli.lib.config import get_manifest_path
from cli.modules.common import console, get_site_context
from cli.modules.page import build_page


def _page_targets(project_root: Path) -> list[Path]:
    return sorted((project_root / "pages").glob("*.html"))


@click.command(name="deploy")
@click.option("--site", "site_name", default=None, help="Configured site name.")
@click.option("--only", "only_module", default="pages")
@click.option("--file", "single_file", default=None, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--dry-run", is_flag=True, default=False)
@click.option("--force", is_flag=True, default=False)
def deploy_command(
    site_name: str | None,
    only_module: str,
    single_file: Path | None,
    dry_run: bool,
    force: bool,
) -> None:
    local_config, _ = get_site_context(site_name)
    project_root = Path(local_config["project_path"]).expanduser()
    manifest_path = get_manifest_path(local_config)
    manifest = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    targets = [single_file] if single_file else _page_targets(project_root)
    if only_module == "all":
        only_module = "pages"
    if only_module != "pages":
        raise click.ClickException(f"Module '{only_module}' is not implemented yet in this repo.")

    planned: list[Path] = []
    for html_file in targets:
        digest = html_file.read_text(encoding="utf-8")
        if force or manifest.get(str(html_file)) != digest:
            planned.append(html_file)

    if dry_run:
        for item in planned:
            console.print(f"Would deploy {item}")
        if not planned:
            console.print("No page changes detected.")
        return

    ctx = click.get_current_context()
    for html_file in planned:
        slug = html_file.stem
        css_file = project_root / "pages-css" / f"{slug}.css"
        ctx.invoke(
            build_page,
            site_name=site_name,
            html_file=html_file,
            css_file=css_file if css_file.exists() else None,
            slug=slug,
            title=slug.replace("-", " ").title(),
            page_status=None,
            publish=False,
            canvas=False,
        )
        manifest[str(html_file)] = html_file.read_text(encoding="utf-8")

    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    if planned:
        console.print(f"[green]Deploy complete[/green] ({len(planned)} page(s))")
    else:
        console.print("No page changes detected.")
