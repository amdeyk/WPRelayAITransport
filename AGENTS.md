# WRS AI Operator Guide

This file is for AI coding/terminal agents operating this repository.

## Mission

Use WP Remote Shell (WRS) to manage WordPress from the local terminal. Treat:

- the local project folder as the source of truth
- the WordPress server as the runtime
- the WRS CLI as the only supported automation interface

Do not assume WordPress Admin is the operating surface.

## Current Implementation Boundary

Implemented and safe to use:

- setup/build flow
- config generation and maintenance
- status/config/server diagnostics
- page build/update/update-css/get/diff/list/publish/clone/set-image/set-meta/delete
- page generate and ai-update through `ai_cli_command`
- journal inspection
- checkpoint inspection
- rollback by checkpoint or recent operation
- pull and pull-all-pages
- page reconciliation

Not implemented end-to-end yet:

- media module
- database module
- members / PMPro module
- email module
- forms / CF7 module
- WooCommerce module
- CPT module
- cron module
- full multi-domain reconciliation

If asked to operate one of the unimplemented modules, say it is not implemented in this repo yet instead of inventing commands.

## First Steps For Every Session

Run these in order before write operations:

```bash
python cli/wrs.py status
python cli/wrs.py config check
python cli/wrs.py circuit-breaker status
python cli/wrs.py reconcile --all
```

If `status` fails, stop and diagnose with:

```bash
python cli/wrs.py server health
python cli/wrs.py server errors
python cli/wrs.py server file-check
```

If the circuit breaker is `OPEN`, do not write. Inspect:

```bash
python cli/wrs.py circuit-breaker history
python cli/wrs.py journal list
python cli/wrs.py checkpoint list
```

Reset only after the root cause is fixed:

```bash
python cli/wrs.py circuit-breaker reset
```

## Safe Defaults

- Prefer read operations before write operations.
- Prefer local file edits plus `page update` over blind remote mutation.
- Prefer `draft` unless the user explicitly wants `publish`.
- Prefer reviewing diffs before publish.
- Prefer `page update-css` for style-only changes.
- Use `rollback --last --dry-run` before an actual rollback when recovering.

## Page Workflows

### Create a page from local files

```bash
python cli/wrs.py page build --file pages/home.html --css pages-css/home.css --slug home --title "Home"
```

### Update an existing page

```bash
python cli/wrs.py page update --file pages/home.html --css pages-css/home.css --slug home
```

### Update only CSS

```bash
python cli/wrs.py page update-css --slug home --css pages-css/home.css
```

### Inspect live state

```bash
python cli/wrs.py page get --slug home
python cli/wrs.py page diff --slug home --file pages/home.html
python cli/wrs.py page list
```

### Publish, clone, image, SEO

```bash
python cli/wrs.py page publish --slug home
python cli/wrs.py page clone --slug home --new-slug home-v2
python cli/wrs.py page set-image --slug home --media-id 42
python cli/wrs.py page set-meta --slug home --title "SEO Title" --description "Meta description"
```

## AI-Assisted Page Generation

WRS can invoke a local AI command stored in `local.config.json` as `ai_cli_command`.

Expected behavior:

- the AI command should return either raw HTML or JSON with `html` and `css`
- WRS writes generated output into the local project files first
- WRS can then deploy the page through the normal checkpoint/journal pipeline

Commands:

```bash
python cli/wrs.py page generate --slug home --prompt "Landing page for a fitness app"
python cli/wrs.py page generate --slug home --prompt "Landing page for a fitness app" --review
python cli/wrs.py page ai-update --slug home --instruction "Add a testimonial section"
```

Use `--review` if the user wants inspection before deployment.

## Deploy Workflows

### Deploy changed pages only

```bash
python cli/wrs.py deploy --only pages
```

### Dry run

```bash
python cli/wrs.py deploy --dry-run
```

### Single file

```bash
python cli/wrs.py deploy --file pages/home.html
```

### Pull live pages into local files

```bash
python cli/wrs.py pull --slug home
python cli/wrs.py pull --all-pages
```

## Recovery Workflows

### Inspect recent operations

```bash
python cli/wrs.py journal list
python cli/wrs.py journal show --op-id <id>
python cli/wrs.py checkpoint list
python cli/wrs.py checkpoint show --checkpoint-id <id>
```

### Roll back

```bash
python cli/wrs.py rollback --last --dry-run
python cli/wrs.py rollback --last
python cli/wrs.py rollback --op-id <id>
python cli/wrs.py rollback --checkpoint-id <id>
```

## How To Interpret Telemetry

Important response fields:

- `status`: `SUCCESS`, `FAILED`, or `PARTIAL`
- `db_rows_affected`: expected write count
- `post_status_after`: resulting WordPress post status
- `wrote_files`: CSS asset files written on the server for enqueue mode
- `content_echo`: preview of server-received content
- `php_errors`: PHP runtime issues
- `warnings`: non-fatal warnings
- `recovery_hint.type`: `SAFE_TO_RETRY`, `DO_NOT_RETRY`, or `NONE`

Rules:

- If `status` is `FAILED`, stop.
- If `status` is `PARTIAL`, treat it as a failure unless the user explicitly decides otherwise.
- If `recovery_hint.type` is `DO_NOT_RETRY`, do not loop.
- Checkpoint-backed rollback is preferred over re-running a broken write blindly.

## Multi-Site Rules

Check the active site before operating:

```bash
python cli/wrs.py sites
python cli/wrs.py use example.com
```

Do not assume the active site is correct in a multi-site environment.

## Config Maintenance

```bash
python setup/wizard.py --rotate-token --site example.com
python setup/wizard.py --only ips --site example.com
python setup/wizard.py --only modules --site example.com
python setup/wizard.py --upgrade --site example.com
python setup/wizard.py --new-site
```

## Constraints

- Do not edit `~/.wrs/sites/<site>/local.config.json` manually unless the user explicitly asks.
- Do not store plaintext tokens in the repo.
- Do not bypass WRS with direct database writes unless the user explicitly requests that level of intervention.
- Do not claim support for modules that are not implemented yet.
- Do not retry failed writes in a loop.

## Good Operator Pattern

1. Inspect state.
2. Pull or diff if necessary.
3. Edit local files.
4. Run the smallest valid WRS command.
5. Read telemetry and journal output.
6. Reconcile if the result is unexpected.
7. Roll back if necessary.

