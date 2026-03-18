# CLI Reference

## Core

- `python cli/wrs.py status`
- `python cli/wrs.py sites`
- `python cli/wrs.py use <site>`
- `python cli/wrs.py config check`
- `python cli/wrs.py setup deploy-config`

## Pages

- `python cli/wrs.py page build --file pages/home.html --slug home --title "Home"`
- `python cli/wrs.py page update --file pages/home.html --slug home`
- `python cli/wrs.py page update-css --slug home --css pages-css/home.css`
- `python cli/wrs.py page build --file pages/home.html --css pages-css/home.css --slug home --title "Home" --publish`
- `python cli/wrs.py page get --slug home`
- `python cli/wrs.py page diff --slug home --file pages/home.html`
- `python cli/wrs.py page list`
- `python cli/wrs.py page publish --slug home`
- `python cli/wrs.py page clone --slug home --new-slug home-v2`
- `python cli/wrs.py page set-image --slug home --media-id 42`
- `python cli/wrs.py page set-meta --slug home --title "SEO Title" --description "Meta description"`
- `python cli/wrs.py page generate --slug home --prompt "Landing page for a fitness app"`
- `python cli/wrs.py page ai-update --slug home --instruction "Add testimonials"`
- `python cli/wrs.py page delete --slug home`

## Deploy

- `python cli/wrs.py deploy --only pages`
- `python cli/wrs.py deploy --only all`
- `python cli/wrs.py deploy --file pages/home.html`
- `python cli/wrs.py deploy --dry-run`
- `python cli/wrs.py pull --slug home`
- `python cli/wrs.py pull --all-pages`
- `python cli/wrs.py diff --slug home --file pages/home.html`

## Circuit breaker

- `python cli/wrs.py circuit-breaker status`
- `python cli/wrs.py circuit-breaker history`
- `python cli/wrs.py circuit-breaker test`
- `python cli/wrs.py circuit-breaker reset`

## Journal / Checkpoints / Recovery

- `python cli/wrs.py journal list`
- `python cli/wrs.py journal show --op-id <id>`
- `python cli/wrs.py journal tail`
- `python cli/wrs.py journal export --output journal.json`
- `python cli/wrs.py checkpoint list`
- `python cli/wrs.py checkpoint show --checkpoint-id <id>`
- `python cli/wrs.py checkpoint clear`
- `python cli/wrs.py rollback --last`
- `python cli/wrs.py rollback --op-id <id>`

## Reconcile / Server

- `python cli/wrs.py reconcile --all`
- `python cli/wrs.py reconcile pages`
- `python cli/wrs.py server health`
- `python cli/wrs.py server errors`
- `python cli/wrs.py server db-status`
- `python cli/wrs.py server file-check`
- `python cli/wrs.py server php-info`
