# AI CLI Playbook

This playbook is the short-form operating manual for AI terminal agents using WP Remote Shell.

Use [AGENTS.md](/D:/wprelay/AGENTS.md) for the full operator guide.

## Objective

Manage WordPress through the WRS CLI only.

- Local files are authoritative.
- WordPress is the runtime.
- Do not invent commands outside the current implementation.

## Supported Areas

Supported now:

- setup and config maintenance
- server diagnostics
- page operations
- deploy for pages
- journal/checkpoint inspection
- rollback
- page reconciliation

Not supported end-to-end:

- media
- database
- members
- email
- forms
- WooCommerce
- CPT
- cron

## Mandatory Preflight

Before any write:

```bash
python cli/wrs.py status
python cli/wrs.py config check
python cli/wrs.py circuit-breaker status
python cli/wrs.py reconcile --all
```

If any command fails, stop and diagnose before writing.

## Read First, Then Write

For existing pages:

```bash
python cli/wrs.py page list
python cli/wrs.py page get --slug <slug>
python cli/wrs.py page diff --slug <slug> --file pages/<slug>.html
```

Prefer understanding live state before mutation.

## Standard Write Recipes

Create a page:

```bash
python cli/wrs.py page build --file pages/<slug>.html --css pages-css/<slug>.css --slug <slug> --title "<Title>"
```

Update a page:

```bash
python cli/wrs.py page update --file pages/<slug>.html --css pages-css/<slug>.css --slug <slug>
```

Update CSS only:

```bash
python cli/wrs.py page update-css --slug <slug> --css pages-css/<slug>.css
```

Publish:

```bash
python cli/wrs.py page publish --slug <slug>
```

Clone:

```bash
python cli/wrs.py page clone --slug <slug> --new-slug <new-slug>
```

Set SEO:

```bash
python cli/wrs.py page set-meta --slug <slug> --title "<SEO Title>" --description "<SEO Description>"
```

Set featured image:

```bash
python cli/wrs.py page set-image --slug <slug> --media-id <id>
```

## AI Generation Recipes

Generate a new page:

```bash
python cli/wrs.py page generate --slug <slug> --prompt "<prompt>"
```

Generate and pause before deploy:

```bash
python cli/wrs.py page generate --slug <slug> --prompt "<prompt>" --review
```

AI update an existing page:

```bash
python cli/wrs.py page ai-update --slug <slug> --instruction "<instruction>"
```

Rules:

- Use `--review` when the user wants approval before pushing.
- Expect the configured AI command to return raw HTML or JSON with `html` and `css`.
- If the AI output is malformed, stop instead of retry-looping.

## Deploy Recipes

Deploy changed pages:

```bash
python cli/wrs.py deploy --only pages
```

Dry run:

```bash
python cli/wrs.py deploy --dry-run
```

Deploy one file:

```bash
python cli/wrs.py deploy --file pages/<slug>.html
```

Pull live pages:

```bash
python cli/wrs.py pull --slug <slug>
python cli/wrs.py pull --all-pages
```

## Recovery Recipes

Inspect:

```bash
python cli/wrs.py journal list
python cli/wrs.py journal show --op-id <id>
python cli/wrs.py checkpoint list
python cli/wrs.py checkpoint show --checkpoint-id <id>
```

Preview rollback:

```bash
python cli/wrs.py rollback --last --dry-run
```

Rollback:

```bash
python cli/wrs.py rollback --last
python cli/wrs.py rollback --op-id <id>
python cli/wrs.py rollback --checkpoint-id <id>
```

## Diagnostics Recipes

```bash
python cli/wrs.py server health
python cli/wrs.py server errors
python cli/wrs.py server db-status
python cli/wrs.py server file-check
python cli/wrs.py server php-info
```

If the circuit is open:

```bash
python cli/wrs.py circuit-breaker history
python cli/wrs.py circuit-breaker test
```

Reset only after the root cause is resolved:

```bash
python cli/wrs.py circuit-breaker reset
```

## Decision Rules

- If a module is not implemented, say so clearly.
- If telemetry says `FAILED`, stop.
- If telemetry says `PARTIAL`, treat it as unsafe until reviewed.
- If `recovery_hint.type` is `DO_NOT_RETRY`, do not retry.
- Prefer rollback over repeated blind writes.
- Prefer file edits plus WRS commands over direct remote mutation.
- Prefer draft over publish unless the user explicitly asks to publish.
- Confirm the active site before operating in multi-site setups.

## Multi-Site Recipe

```bash
python cli/wrs.py sites
python cli/wrs.py use <site>
python cli/wrs.py status
```

## Config Maintenance Recipes

```bash
python setup/wizard.py --rotate-token --site <site>
python setup/wizard.py --only ips --site <site>
python setup/wizard.py --only modules --site <site>
python setup/wizard.py --upgrade --site <site>
python setup/wizard.py --new-site
```

## Unsafe Patterns

Do not:

- bypass WRS with direct database writes unless explicitly instructed
- assume unsupported modules exist
- retry failed writes in a loop
- edit local token storage casually
- publish by default when the user did not ask for it

