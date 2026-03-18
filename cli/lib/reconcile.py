from __future__ import annotations

from pathlib import Path


def reconcile_pages(project_root: Path, remote_pages: list[dict]) -> list[dict]:
    results: list[dict] = []
    by_slug = {item["slug"]: item for item in remote_pages}
    local_slugs = {path.stem for path in (project_root / "pages").glob("*.html")}

    for slug in sorted(local_slugs):
        results.append({"slug": slug, "state": "MATCH" if slug in by_slug else "LOCAL_ONLY"})
    for slug in sorted(set(by_slug) - local_slugs):
        results.append({"slug": slug, "state": "SERVER_ONLY"})
    return results

