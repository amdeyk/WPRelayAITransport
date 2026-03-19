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
- preflight checks — run before every session
- status/config/server diagnostics
- page build/update/update-css/get/diff/list/list-all/publish/clone/set-image/set-meta/delete
- page inspect — full inspection of any page by slug, ID, or front-page (`--front`)
- page adopt — explicitly mark an unmanaged page as WRS-managed
- page css-override — inject CSS into any page without adoption or content changes
- page elementor-get — download Elementor JSON data for a page
- page elementor-set — upload Elementor JSON data back to a live page
- page generate and ai-update through `ai_cli_command`
- journal inspection
- checkpoint inspection (checkpoints now include Elementor data)
- rollback by checkpoint or recent operation (handles HTML and Elementor pages)
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
python cli/wrs.py preflight
python cli/wrs.py reconcile --all
```

The preflight checks: local config, site reachability, plugin authentication, server health, server config file, circuit breaker state, content module status, and PHP environment. If any check fails, stop and address the reported issue before proceeding.

If `preflight` fails on `Plugin ping (auth)`, diagnose with:

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

- Run preflight before every session.
- Prefer read operations before write operations.
- Prefer local file edits plus `page update` over blind remote mutation.
- Prefer `draft` unless the user explicitly wants `publish`.
- Prefer reviewing diffs before publish.
- Prefer `page update-css` or `page css-override` for style-only changes.
- Use `rollback --last --dry-run` before an actual rollback when recovering.
- Never run `page build` or `page update` on a page that reports `builder = elementor`.

## Page Workflows

### Create a page from local files

```bash
python cli/wrs.py page build --file pages/home.html --css pages-css/home.css --slug home --title "Home"
```

### Update an existing WRS-managed page

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
python cli/wrs.py page list --all
```

### Publish, clone, image, SEO

```bash
python cli/wrs.py page publish --slug home
python cli/wrs.py page clone --slug home --new-slug home-v2
python cli/wrs.py page set-image --slug home --media-id 42
python cli/wrs.py page set-meta --slug home --title "SEO Title" --description "Meta description"
```

## Inspecting Unmanaged or Unknown Pages

Before working with any existing WordPress page that WRS did not create, inspect it first:

```bash
python cli/wrs.py page inspect --slug home-2
python cli/wrs.py page inspect --id 1167
python cli/wrs.py page inspect --front
```

The inspection output tells you:
- `is_wrs_managed`: whether WRS owns the page
- `builder`: `elementor` or `none`
- `is_front_page`: whether it is the static front page
- `has_wrs_source`: whether WRS source HTML is stored
- `has_wrs_css_override`: whether a CSS override is active
- `has_elementor_data`: whether Elementor JSON data exists on the server

## Adopting an Existing Page

Adoption is required before running content edits on an unmanaged page. It is an explicit step — pages should not silently become managed.

```bash
python cli/wrs.py page adopt --slug home-2
python cli/wrs.py page adopt --id 1167
```

Adoption sets `_wrs_managed`, records the page mode (`html` or `elementor`), and creates a checkpoint. For Elementor pages it does not touch builder data.

Do not adopt a page and then immediately run `page build` or `page update` on it if `builder = elementor`. Use `page elementor-set` instead.

## CSS Override (Safe For Elementor Pages)

To make visual changes to any live page without taking over its content:

```bash
python cli/wrs.py page css-override --slug home-2 --css overrides/welcome-color.css
```

This injects CSS via `wp_head`. It does not affect Elementor data or the page template. No adoption required. A checkpoint is created before the CSS is written.

## Elementor Page Workflows

### Download Elementor JSON

```bash
python cli/wrs.py page elementor-get --slug home-2
python cli/wrs.py page elementor-get --id 1167
python cli/wrs.py page elementor-get --slug home-2 --output elementor/home-2.json
```

The saved JSON contains `elementor_data` (the widget tree) and `page_settings`.

### Upload modified Elementor JSON

```bash
python cli/wrs.py page elementor-set --slug home-2 --file elementor/home-2.json
```

This updates `_elementor_data` on the live page and clears Elementor's CSS cache. It does not overwrite `post_content`. A checkpoint is created before writing.

### Constraints for Elementor pages

- Do not use `page build` or `page update` on Elementor pages. Those commands write HTML content and will destroy the Elementor structure.
- Do not set `_wrs_canvas` on Elementor pages. This is handled automatically.
- Elementor's CSS regenerates on the next page view after `elementor-set`. If it looks stale, tell the user to hard-reload.

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

Rollback correctly handles both HTML and Elementor pages. For Elementor pages it restores `_elementor_data` and clears the CSS cache without touching `post_content`.

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

- Run preflight before every session.
- Do not edit `~/.wrs/sites/<site>/local.config.json` manually unless the user explicitly asks.
- Do not store plaintext tokens in the repo.
- Do not bypass WRS with direct database writes unless the user explicitly requests that level of intervention.
- Do not claim support for modules that are not implemented yet.
- Do not retry failed writes in a loop.
- Do not use `page build` or `page update` on Elementor pages.
- Do not adopt a page silently — adoption must be an explicit deliberate step.

## Good Operator Pattern

1. Run preflight.
2. Inspect state (page inspect, page list --all, page diff).
3. Pull or diff if necessary.
4. Edit local files.
5. Run the smallest valid WRS command.
6. Read telemetry and journal output.
7. Reconcile if the result is unexpected.
8. Roll back if necessary.
