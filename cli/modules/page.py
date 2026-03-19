from __future__ import annotations

import difflib
import json
import subprocess
from pathlib import Path

import click
from rich.table import Table

from cli.modules.common import console, get_site_context, resolve_project_file, run_write_operation


def _read_optional_text(path: Path | None) -> str:
    if path is None or not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _build_payload(local_config: dict, html_file: Path, css_file: Path | None, slug: str, title: str, status: str, canvas: bool) -> dict:
    return {
        "slug": slug,
        "title": title,
        "html": html_file.read_text(encoding="utf-8"),
        "css": _read_optional_text(css_file),
        "status": status,
        "canvas": canvas,
        "page_mode": local_config.get("page_mode", "html"),
        "css_mode": local_config.get("css_mode", "inline"),
    }


def _write_page_files(local_config: dict, slug: str, html: str, css: str = "") -> tuple[Path, Path]:
    html_path = resolve_project_file(local_config, f"pages/{slug}.html")
    css_path = resolve_project_file(local_config, f"pages-css/{slug}.css")
    html_path.parent.mkdir(parents=True, exist_ok=True)
    css_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html, encoding="utf-8")
    if css:
        css_path.write_text(css, encoding="utf-8")
    return html_path, css_path


def _run_ai(local_config: dict, prompt: str) -> tuple[str, str]:
    command = (local_config.get("ai_cli_command") or "").strip()
    if not command:
        raise click.ClickException(
            "No AI CLI command is configured for this site. Run `python setup/wizard.py` for a new site or set `ai_cli_command` in the site config."
        )
    result = subprocess.run(
        command,
        input=prompt,
        text=True,
        capture_output=True,
        shell=True,
        check=False,
    )
    if result.returncode != 0:
        raise click.ClickException(result.stderr.strip() or "AI command failed.")
    stdout = result.stdout.strip()
    if not stdout:
        return "", ""
    try:
        payload = json.loads(stdout)
        return payload.get("html", ""), payload.get("css", "")
    except json.JSONDecodeError:
        return stdout, ""


@click.group(name="page")
def page_group() -> None:
    """Page content commands."""


@page_group.command("build")
@click.option("--site", "site_name", default=None, help="Configured site name.")
@click.option("--file", "html_file", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--css", "css_file", default=None, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--slug", required=True)
@click.option("--title", required=True)
@click.option("--status", "page_status", default=None)
@click.option("--publish", is_flag=True, default=False)
@click.option("--canvas", is_flag=True, default=False)
def build_page(
    site_name: str | None,
    html_file: Path,
    css_file: Path | None,
    slug: str,
    title: str,
    page_status: str | None,
    publish: bool,
    canvas: bool,
) -> None:
    local_config, client = get_site_context(site_name)
    status = "publish" if publish else (page_status or local_config.get("default_status", "draft"))
    payload = _build_payload(local_config, html_file, css_file, slug, title, status, canvas)
    response = run_write_operation(
        local_config["site_name"],
        local_config,
        client,
        op_type="page.build",
        endpoint="/content/page/apply",
        payload=payload,
        checkpoint_targets={"kind": "page", "slug": slug},
        payload_summary=f"{slug} ({status})",
    )
    console.print(f"[green]Page synced[/green] {slug} -> id {response.get('page', {}).get('id')}")


@page_group.command("update")
@click.option("--site", "site_name", default=None, help="Configured site name.")
@click.option("--file", "html_file", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--css", "css_file", default=None, type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--slug", required=True)
@click.option("--title", default=None)
def update_page(site_name: str | None, html_file: Path, css_file: Path | None, slug: str, title: str | None) -> None:
    local_config, client = get_site_context(site_name)
    current = client.request("GET", "/content/page/get", params={"slug": slug})["page"]
    payload = _build_payload(
        local_config,
        html_file,
        css_file,
        slug,
        title or current.get("title") or slug.replace("-", " ").title(),
        current.get("status", "draft"),
        current.get("canvas", False),
    )
    response = run_write_operation(
        local_config["site_name"],
        local_config,
        client,
        op_type="page.update",
        endpoint="/content/page/apply",
        payload=payload,
        checkpoint_targets={"kind": "page", "slug": slug},
        payload_summary=f"{slug} update",
    )
    console.print(f"[green]Page updated[/green] {slug} -> id {response.get('page', {}).get('id')}")


@page_group.command("update-css")
@click.option("--site", "site_name", default=None, help="Configured site name.")
@click.option("--slug", required=True)
@click.option("--css", "css_file", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
def update_css(site_name: str | None, slug: str, css_file: Path) -> None:
    local_config, client = get_site_context(site_name)
    response = run_write_operation(
        local_config["site_name"],
        local_config,
        client,
        op_type="page.update-css",
        endpoint="/content/page/update-css",
        payload={"slug": slug, "css": css_file.read_text(encoding="utf-8"), "css_mode": local_config.get("css_mode", "inline")},
        checkpoint_targets={"kind": "page", "slug": slug},
        payload_summary=f"{slug} css",
    )
    console.print(f"[green]CSS updated[/green] {slug} -> id {response.get('page', {}).get('id')}")


@page_group.command("get")
@click.option("--site", "site_name", default=None, help="Configured site name.")
@click.option("--slug", required=True)
@click.option("--output", default=None, type=click.Path(dir_okay=False, path_type=Path))
def get_page(site_name: str | None, slug: str, output: Path | None) -> None:
    local_config, client = get_site_context(site_name)
    response = client.request("GET", "/content/page/get", params={"slug": slug})
    page = response["page"]
    if output is None:
        output = resolve_project_file(local_config, f"pages/{slug}.html")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(page["html"], encoding="utf-8")
    if page.get("css"):
        resolve_project_file(local_config, f"pages-css/{slug}.css").write_text(page["css"], encoding="utf-8")
    console.print(f"[green]Saved[/green] {slug} to {output}")


@page_group.command("diff")
@click.option("--site", "site_name", default=None, help="Configured site name.")
@click.option("--slug", required=True)
@click.option("--file", "html_file", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
def diff_page(site_name: str | None, slug: str, html_file: Path) -> None:
    _, client = get_site_context(site_name)
    response = client.request("GET", "/content/page/get", params={"slug": slug})
    live_html = response["page"]["html"].splitlines()
    local_html = html_file.read_text(encoding="utf-8").splitlines()
    diff = difflib.unified_diff(live_html, local_html, fromfile="live", tofile=str(html_file), lineterm="")
    console.print("\n".join(diff) or "No differences.")


@page_group.command("list")
@click.option("--site", "site_name", default=None, help="Configured site name.")
@click.option("--all", "all_pages", is_flag=True, default=False, help="List all pages, not just WRS-managed ones.")
def list_pages(site_name: str | None, all_pages: bool) -> None:
    _, client = get_site_context(site_name)
    params = {"all": "1"} if all_pages else {}
    response = client.request("GET", "/content/page/list", params=params)
    if all_pages:
        columns = ("id", "slug", "title", "status", "builder", "is_wrs_managed", "is_front_page")
        title = "All Pages"
    else:
        columns = ("id", "slug", "title", "status", "mode", "modified")
        title = "Managed Pages"
    table = Table(title=title)
    for column in columns:
        table.add_column(column)
    for page in response.get("pages", []):
        table.add_row(*[str(page.get(c, "")) for c in columns])
    console.print(table)


@page_group.command("publish")
@click.option("--site", "site_name", default=None, help="Configured site name.")
@click.option("--slug", required=True)
def publish_page(site_name: str | None, slug: str) -> None:
    local_config, client = get_site_context(site_name)
    response = run_write_operation(
        local_config["site_name"],
        local_config,
        client,
        op_type="page.publish",
        endpoint="/content/page/publish",
        payload={"slug": slug},
        checkpoint_targets={"kind": "page", "slug": slug},
        payload_summary=f"{slug} publish",
    )
    console.print(f"[green]Published[/green] {slug} ({response.get('page', {}).get('id')})")


@page_group.command("clone")
@click.option("--site", "site_name", default=None, help="Configured site name.")
@click.option("--slug", required=True)
@click.option("--new-slug", required=True)
@click.option("--new-title", default=None)
def clone_page(site_name: str | None, slug: str, new_slug: str, new_title: str | None) -> None:
    local_config, client = get_site_context(site_name)
    response = run_write_operation(
        local_config["site_name"],
        local_config,
        client,
        op_type="page.clone",
        endpoint="/content/page/clone",
        payload={"slug": slug, "new_slug": new_slug, "new_title": new_title or ""},
        checkpoint_targets={"kind": "page", "slug": slug},
        payload_summary=f"{slug} -> {new_slug}",
    )
    console.print(f"[green]Cloned[/green] {slug} -> {response.get('page', {}).get('slug')}")


@page_group.command("set-image")
@click.option("--site", "site_name", default=None, help="Configured site name.")
@click.option("--slug", required=True)
@click.option("--media-id", required=True, type=int)
def set_image(site_name: str | None, slug: str, media_id: int) -> None:
    local_config, client = get_site_context(site_name)
    response = run_write_operation(
        local_config["site_name"],
        local_config,
        client,
        op_type="page.set-image",
        endpoint="/content/page/set-image",
        payload={"slug": slug, "media_id": media_id},
        checkpoint_targets={"kind": "page", "slug": slug},
        payload_summary=f"{slug} image {media_id}",
    )
    console.print(f"[green]Featured image set[/green] {slug} -> {response.get('page', {}).get('featured_image_id')}")


@page_group.command("set-meta")
@click.option("--site", "site_name", default=None, help="Configured site name.")
@click.option("--slug", required=True)
@click.option("--title", default="")
@click.option("--description", default="")
def set_meta(site_name: str | None, slug: str, title: str, description: str) -> None:
    local_config, client = get_site_context(site_name)
    response = run_write_operation(
        local_config["site_name"],
        local_config,
        client,
        op_type="page.set-meta",
        endpoint="/content/page/set-meta",
        payload={"slug": slug, "title": title, "description": description},
        checkpoint_targets={"kind": "page", "slug": slug},
        payload_summary=f"{slug} seo",
    )
    console.print(f"[green]SEO meta updated[/green] {slug} -> {response.get('page', {}).get('seo_title')}")


@page_group.command("generate")
@click.option("--site", "site_name", default=None, help="Configured site name.")
@click.option("--slug", required=True)
@click.option("--prompt", required=True)
@click.option("--publish", is_flag=True, default=False)
@click.option("--review", is_flag=True, default=False)
def generate_page(site_name: str | None, slug: str, prompt: str, publish: bool, review: bool) -> None:
    local_config, _ = get_site_context(site_name)
    full_prompt = (
        f"Create a WordPress-ready HTML page for slug '{slug}'. "
        "Return JSON with keys html and css. "
        f"Request: {prompt}"
    )
    html, css = _run_ai(local_config, full_prompt)
    if not html:
        raise click.ClickException("AI command returned no HTML.")
    html_path, css_path = _write_page_files(local_config, slug, html, css)
    console.print(f"[green]Generated[/green] {html_path}")
    if review:
        return
    ctx = click.get_current_context()
    ctx.invoke(
        build_page,
        site_name=site_name,
        html_file=html_path,
        css_file=css_path if css_path.exists() else None,
        slug=slug,
        title=slug.replace("-", " ").title(),
        page_status=None,
        publish=publish,
        canvas=False,
    )


@page_group.command("ai-update")
@click.option("--site", "site_name", default=None, help="Configured site name.")
@click.option("--slug", required=True)
@click.option("--instruction", required=True)
@click.option("--review", is_flag=True, default=False)
def ai_update(site_name: str | None, slug: str, instruction: str, review: bool) -> None:
    local_config, client = get_site_context(site_name)
    current = client.request("GET", "/content/page/get", params={"slug": slug})["page"]
    prompt = (
        "Update the following page HTML. Return JSON with keys html and css. "
        f"Instruction: {instruction}\n\nHTML:\n{current['html']}\n\nCSS:\n{current.get('css', '')}"
    )
    html, css = _run_ai(local_config, prompt)
    if not html:
        raise click.ClickException("AI command returned no HTML.")
    html_path, css_path = _write_page_files(local_config, slug, html, css or current.get("css", ""))
    console.print(f"[green]AI updated[/green] {html_path}")
    if review:
        return
    ctx = click.get_current_context()
    ctx.invoke(update_page, site_name=site_name, html_file=html_path, css_file=css_path, slug=slug, title=current.get("title"))


@page_group.command("delete")
@click.option("--site", "site_name", default=None, help="Configured site name.")
@click.option("--slug", required=True)
def delete_page(site_name: str | None, slug: str) -> None:
    local_config, client = get_site_context(site_name)
    run_write_operation(
        local_config["site_name"],
        local_config,
        client,
        op_type="page.delete",
        endpoint="/content/page/delete",
        payload={"slug": slug},
        checkpoint_targets={"kind": "page", "slug": slug},
        payload_summary=f"{slug} delete",
    )
    console.print(f"[green]Deleted[/green] {slug}")


@page_group.command("inspect")
@click.option("--site", "site_name", default=None, help="Configured site name.")
@click.option("--slug", default=None, help="Page slug.")
@click.option("--id", "page_id", default=None, type=int, help="Page ID.")
@click.option("--front", is_flag=True, default=False, help="Inspect the static front page (resolves / automatically).")
def inspect_page(site_name: str | None, slug: str | None, page_id: int | None, front: bool) -> None:
    """Inspect any page: builder type, WRS ownership, source availability."""
    _, client = get_site_context(site_name)
    params: dict = {}
    if front:
        params["front"] = "1"
    elif page_id:
        params["id"] = page_id
    elif slug:
        params["slug"] = slug
    else:
        raise click.ClickException("Provide --slug, --id, or --front.")
    response = client.request("GET", "/content/page/inspect", params=params)
    page = response["page"]
    table = Table(title=f"Page Inspection: {page.get('title', '')}")
    table.add_column("Field")
    table.add_column("Value")
    for key, val in page.items():
        table.add_row(key, str(val) if val is not None else "—")
    console.print(table)


@page_group.command("adopt")
@click.option("--site", "site_name", default=None, help="Configured site name.")
@click.option("--slug", default=None, help="Page slug.")
@click.option("--id", "page_id", default=None, type=int, help="Page ID.")
def adopt_page(site_name: str | None, slug: str | None, page_id: int | None) -> None:
    """Mark an existing unmanaged page as WRS-managed (required before content edits)."""
    local_config, client = get_site_context(site_name)
    payload: dict = {}
    if page_id:
        payload["id"] = page_id
        ident = str(page_id)
    elif slug:
        payload["slug"] = slug
        ident = slug
    else:
        raise click.ClickException("Provide --slug or --id.")
    response = run_write_operation(
        local_config["site_name"],
        local_config,
        client,
        op_type="page.adopt",
        endpoint="/content/page/adopt",
        payload=payload,
        checkpoint_targets={"kind": "page", "slug": ident},
        payload_summary=f"{ident} adopt",
    )
    page = response.get("page", {})
    console.print(
        f"[green]Adopted[/green] id={page.get('id')} slug={page.get('slug')} "
        f"builder={page.get('builder')} mode={page.get('mode')}"
    )


@page_group.command("css-override")
@click.option("--site", "site_name", default=None, help="Configured site name.")
@click.option("--slug", required=True, help="Page slug (e.g. home-2 for the front page).")
@click.option("--css", "css_file", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path))
def css_override(site_name: str | None, slug: str, css_file: Path) -> None:
    """Inject CSS overrides into any page without adopting or changing its content.

    Safe to use on Elementor pages. The CSS is injected via wp_head and does not
    affect the page builder data or template.
    """
    local_config, client = get_site_context(site_name)
    response = run_write_operation(
        local_config["site_name"],
        local_config,
        client,
        op_type="page.css-override",
        endpoint="/content/page/update-css",
        payload={"slug": slug, "css": css_file.read_text(encoding="utf-8"), "css_mode": local_config.get("css_mode", "inline")},
        checkpoint_targets={"kind": "page", "slug": slug},
        payload_summary=f"{slug} css-override",
    )
    console.print(f"[green]CSS override applied[/green] {slug} (id={response.get('page', {}).get('id')})")


@page_group.command("elementor-get")
@click.option("--site", "site_name", default=None, help="Configured site name.")
@click.option("--slug", default=None, help="Page slug.")
@click.option("--id", "page_id", default=None, type=int, help="Page ID.")
@click.option("--output", default=None, type=click.Path(dir_okay=False, path_type=Path), help="Output JSON file path.")
def elementor_get(site_name: str | None, slug: str | None, page_id: int | None, output: Path | None) -> None:
    """Download Elementor JSON data for a page to a local file."""
    local_config, client = get_site_context(site_name)
    params: dict = {}
    if page_id:
        params["id"] = page_id
    elif slug:
        params["slug"] = slug
    else:
        raise click.ClickException("Provide --slug or --id.")
    response = client.request("GET", "/content/page/elementor/get", params=params)
    artifact = {
        "page_id": response["page_id"],
        "slug": response["slug"],
        "title": response["title"],
        "elementor_data": response["elementor_data"],
        "page_settings": response["page_settings"],
    }
    if output is None:
        out_slug = response.get("slug") or str(response.get("page_id", "page"))
        output = resolve_project_file(local_config, f"elementor/{out_slug}.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, indent=2, ensure_ascii=False), encoding="utf-8")
    console.print(f"[green]Saved[/green] Elementor data ({response['slug']}) -> {output}")


@page_group.command("elementor-set")
@click.option("--site", "site_name", default=None, help="Configured site name.")
@click.option("--slug", default=None, help="Page slug.")
@click.option("--id", "page_id", default=None, type=int, help="Page ID.")
@click.option("--file", "json_file", required=True, type=click.Path(exists=True, dir_okay=False, path_type=Path),
              help="JSON file produced by elementor-get (or a raw elementor_data array).")
def elementor_set(site_name: str | None, slug: str | None, page_id: int | None, json_file: Path) -> None:
    """Upload Elementor JSON data to a live page. Clears Elementor's CSS cache."""
    local_config, client = get_site_context(site_name)
    raw = json.loads(json_file.read_text(encoding="utf-8"))
    # Accept either a raw array (elementor_data only) or the full artifact from elementor-get.
    if isinstance(raw, list):
        elementor_data = raw
        page_settings: dict = {}
    else:
        elementor_data = raw.get("elementor_data", raw)
        page_settings = raw.get("page_settings", {})
    payload: dict = {"elementor_data": elementor_data, "page_settings": page_settings}
    if page_id:
        payload["id"] = page_id
        ident = str(page_id)
    elif slug:
        payload["slug"] = slug
        ident = slug
    else:
        raise click.ClickException("Provide --slug or --id.")
    response = run_write_operation(
        local_config["site_name"],
        local_config,
        client,
        op_type="page.elementor-set",
        endpoint="/content/page/elementor/set",
        payload=payload,
        checkpoint_targets={"kind": "page", "slug": ident},
        payload_summary=f"{ident} elementor-set",
    )
    console.print(f"[green]Elementor data applied[/green] {response.get('slug')} (id={response.get('page_id')})")
