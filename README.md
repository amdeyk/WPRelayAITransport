# WP Remote Shell

WP Remote Shell (WRS) is a CLI-first WordPress operations system.

It lets you build and update WordPress pages from local files and push those changes through a signed API bridge instead of using the WordPress Admin for day-to-day editing. It also supports inspecting, adopting, and managing Elementor pages without destroying their builder data.

Today this repository is strongest in one complete vertical slice:

- setup and packaging
- authenticated transport
- journaling and checkpoints
- rollback support
- page build / update / publish workflows
- page inspection and adoption for unmanaged and builder-based pages
- CSS overrides for any page (including Elementor pages)
- Elementor page read/write via JSON data
- AI-assisted page generation and update
- CLI pairing (connect a new machine without running the full wizard)
- disconnect and server-side token revocation
- preflight checks — verify the full stack before operating

The larger product vision includes many more modules, but this repo currently centers on safe WordPress page operations.

## What WRS Does

WRS changes the normal WordPress workflow from:

```text
Browser -> WordPress Admin -> Manual edits -> Hope nothing breaks
```

to:

```text
Local files -> WRS CLI -> Signed request -> WRS plugin -> WordPress runtime
```

That means:

- your HTML/CSS lives locally and can be versioned in git
- each write operation is journaled before it happens
- a checkpoint is created before every change
- rollback is a single command if something goes wrong
- an AI CLI can operate through the same commands instead of inventing its own flow
- Elementor pages can be inspected and managed without converting them to plain HTML

## Architecture

```text
                         WP REMOTE SHELL
    -------------------------------------------------------------

      Local Machine                               WordPress Server
    -----------------                           -------------------

    pages/home.html
    pages-css/home.css
    elementor/home-2.json
    journal.ndjson
    circuit.json
    local.config.json
           |
           |  python cli/wrs.py page build ...
           v
    +------------------+
    |   WRS CLI        |
    |------------------|
    | config loader    |
    | HMAC signer      |
    | journal writer   |
    | checkpoint client|
    | circuit breaker  |
    | preflight checks |
    +------------------+
           |
           | HTTPS + token + HMAC + timestamp + IP allowlist
           v
    +------------------+
    | WRS WP Plugin    |
    |------------------|
    | auth gate        |
    | router           |
    | content module   |
    | elementor module |
    | telemetry        |
    | checkpoint store |
    | server journal   |
    +------------------+
           |
           v
    +------------------+
    | WordPress        |
    |------------------|
    | pages            |
    | post meta        |
    | elementor meta   |
    | theme rendering  |
    +------------------+
```

## Current Scope

Implemented and working now:

- setup wizard and config generation
- plugin ZIP packaging
- per-site local and server config handling
- CLI pairing code — connect a new machine without re-running the wizard
- authenticated transport with:
  - HTTPS enforcement
  - IP allowlist
  - bcrypt token verification
  - HMAC-SHA256 request signing
  - replay window checks
  - replay cache
  - rate limiting
  - master enable switch
- local journal
- circuit breaker
- server-side checkpoints (including Elementor data snapshots)
- rollback from checkpoints (HTML and Elementor pages)
- preflight checks — end-to-end validation before operating
- page operations:
  - build
  - update
  - update-css
  - get
  - diff
  - list / list --all (all pages, not just managed ones)
  - publish
  - clone
  - set-image
  - set-meta
  - delete
  - generate (AI)
  - ai-update (AI)
  - inspect — full inspection of any page by slug, ID, or front-page
  - adopt — explicitly mark an unmanaged page as WRS-managed
  - css-override — inject CSS into any page without adoption
  - elementor-get — download Elementor JSON data for a page
  - elementor-set — upload Elementor JSON data back to a live page
- server diagnostics:
  - health
  - errors
  - db-status
  - file-check
  - php-info
- page-only deploy flow
- pull and pull-all-pages
- page reconciliation
- disconnect with optional server-side token revocation

Not fully implemented yet:

- media module
- database / migrations module
- members / PMPro module
- email module
- forms / CF7 module
- WooCommerce module
- CPT module
- cron module
- full cross-module reconciliation

## Repository Layout

```text
.
|-- AGENTS.md                    AI operator guide
|-- README.md                    this file
|-- requirements.txt             Python dependencies
|-- cli/
|   |-- wrs.py                   main CLI entrypoint
|   |-- lib/                     config, HTTP, journal, checkpoint, circuit logic
|   `-- modules/                 page, server, setup, connect, preflight, rollback, reconcile, etc.
|-- plugin/
|   |-- wp-remote-shell.php      plugin bootstrap (v0.2.0)
|   |-- includes/                auth, router, telemetry, checkpoint helpers
|   |-- modules/                 WordPress capability modules
|   |-- admin/                   WordPress admin settings page
|   |-- schema/                  SQL install/uninstall definitions
|   `-- templates/               canvas template
|-- setup/
|   |-- wizard.py                interactive setup + maintenance wizard
|   |-- build_config.py          config creation helpers
|   `-- build_plugin.py          plugin ZIP packaging
|-- config/
|   |-- local.config.template.json
|   `-- plugin.config.template.json
|-- templates/                   starter HTML/CSS page templates
`-- docs/                        install, CLI, security, recovery, AI docs
```

## The Main Idea

```text
You do not "edit WordPress directly".

You:
1. edit files locally
2. review the files
3. run WRS commands
4. let WRS push those files safely into WordPress
5. inspect telemetry and journal output
```

That is the mental model both humans and AI agents should use.

---

## First-Time Installation

This section assumes:

- you have Python installed
- you have a WordPress site already running
- you can log in to WordPress Admin
- you can edit `wp-config.php` on the server once

### Step 1: Get the repository

```bash
git clone <your-repo-url>
cd wp-remote-shell
```

### Step 2: Install Python dependencies

```bash
pip install -r requirements.txt
```

### Step 3: Run the setup wizard

```bash
python setup/wizard.py
```

The wizard runs through **8 numbered steps** and explains each choice before asking for it:

| Step | What it sets up |
|------|-----------------|
| 1 — Site URL | Validates and normalises your WordPress URL, derives the site folder name |
| 2 — Project | Local folder where your HTML, CSS, and content files will live |
| 3 — Access | IP allowlist — start open, lock it down later |
| 4 — Authentication | Auto-generates a 64-char hex token or accepts a manual one (16+ chars) |
| 5 — Safety | Circuit-breaker reset PIN (digits only, 6+ chars, confirmed twice) |
| 6 — Content Defaults | Page mode (html/elementor), CSS mode (inline/enqueue), default status |
| 7 — AI | Optional AI CLI command for `page generate` and `page ai-update` |
| 8 — Modules | Which modules to enable — only `content` is fully implemented |

A review table is shown before any files are written. Press Enter to accept the default shown in brackets at each prompt.

### Step 4: What the wizard creates

```text
~/.wrs/sites/<site>/local.config.json      local plaintext config
~/.wrs/sites/<site>/plugin.config.json     server config reference copy
setup/output/<site>/wp-remote-shell.zip    plugin ZIP to upload to WordPress
setup/output/<site>/wp-config-line.txt     one line to add to wp-config.php
<project_path>/pages/                      local page HTML files go here
<project_path>/pages-css/                  local page CSS files go here
<project_path>/elementor/                  local Elementor JSON files go here
```

`<site>` is derived from your WordPress URL. `https://example.com` becomes `example.com`.

### Step 5: Upload the plugin in WordPress

1. Log in to WordPress Admin.
2. Go to **Plugins → Add New Plugin → Upload Plugin**.
3. Choose `setup/output/<site>/wp-remote-shell.zip`.
4. Click **Install Now**, then **Activate Plugin**.

After activation a **WP Remote Shell** menu appears in the left admin sidebar.

Upload the `.zip` itself — do not unzip it first. `plugin.config.json` is not the file you upload in this step.

### Step 6: Add the config path to `wp-config.php`

Open `setup/output/<site>/wp-config-line.txt`. It contains one line:

```php
define('WRS_CONFIG_PATH', dirname(__FILE__) . '/wp-content/uploads/wrs/plugin.config.json');
```

Paste that line into `wp-config.php` above the `/* That's all, stop editing! */` comment.

### Step 7: Deploy the server config

```bash
python cli/wrs.py setup deploy-config
```

### Step 8: Run the preflight check

```bash
python cli/wrs.py preflight
```

The preflight runs **8 checks** in sequence and prints a pass/fail table:

| Check | What it verifies |
|-------|-----------------|
| Local config | Required fields are present in `~/.wrs/sites/<site>/local.config.json` |
| Site reachable | The site URL responds over HTTP |
| Plugin ping (auth) | An authenticated request reaches the WRS plugin and the token is valid |
| Server health | Server reports `status=ok` |
| Server config file | `plugin.config.json` exists on the server at the expected path |
| Circuit breaker | The circuit breaker is CLOSED (writes are allowed) |
| Content module | The content module is enabled in the server config |
| PHP environment | Reports PHP version, memory limit, and max execution time (informational) |

If all checks pass, you are ready to operate. Any failure shows the exact reason and which remediation to run.

---

## Connecting From A New Machine (Pairing)

If you need to connect a different computer to a WordPress site that is already running WRS — without re-running the full wizard — use the pairing code flow.

### In WordPress Admin

1. Go to **WP Remote Shell** in the admin sidebar.
2. Find the **CLI Pairing Code** card.
3. Click **Generate CLI Pairing Code**.
4. The card shows a hex code and the exact command to run. Copy the command.

The code expires in **30 minutes** and works **only once**. Generating a new code invalidates any previous one.

### In your terminal

Paste the command shown in WordPress:

```bash
python cli/wrs.py pair <hex-code>
```

The wizard asks for two things the server cannot know — your local project path and a circuit-breaker PIN — then writes the local config automatically.

Confirm the connection with the preflight check:

```bash
python cli/wrs.py preflight
```

### How pairing works (for reference)

```text
WordPress admin generates a one-time nonce
  -> stores it server-side for 30 minutes
  -> encodes {site_url, nonce} as a hex string

CLI decodes the hex string
  -> POSTs the nonce to /wp-json/wrs/v1/connect/pair (no HMAC needed)

Plugin validates the nonce, deletes it (single-use)
  -> generates a fresh 64-char token
  -> stores its bcrypt hash in plugin.config.json
  -> returns the plaintext token to the CLI

CLI saves the token in ~/.wrs/sites/<site>/local.config.json
  -> sets as active site
```

---

## Disconnecting

### Remove local credentials only

```bash
python cli/wrs.py disconnect
python cli/wrs.py disconnect --site example.com
```

This deletes `~/.wrs/sites/<site>/` and updates the active-site pointer. The server token remains valid (useful if you want to re-pair on this machine later with `pair`).

### Revoke the server token too

```bash
python cli/wrs.py disconnect --revoke
```

This makes an authenticated request to clear the token hash and disable the plugin API server-side before removing local files. Use this when decommissioning a site or handing it off.

---

## Safe Operating Pattern

Use this order every time:

```bash
python cli/wrs.py preflight
python cli/wrs.py reconcile --all
```

Then:

```text
1. read live state if needed
2. edit local files
3. push the smallest valid change
4. inspect telemetry and journal
5. roll back if necessary
```

If the preflight fails, stop and fix the reported issue before writing anything. Do not bypass the preflight by running write commands directly.

---

## Local Project Folder

```text
<project_path>/
|-- pages/
|   |-- home.html
|   |-- about.html
|   `-- contact.html
|-- pages-css/
|   |-- home.css
|   |-- about.css
|   `-- contact.css
|-- elementor/
|   `-- home-2.json            Elementor page JSON (from page elementor-get)
|-- partials/
|-- posts/
|-- media/
|-- migrations/
`-- wrs-manifest.json
```

For the current implementation `pages/`, `pages-css/`, and `elementor/` are the most important directories.

---

## Page Commands

### Create a page

```bash
python cli/wrs.py page build \
  --file pages/home.html \
  --css pages-css/home.css \
  --slug home \
  --title "Home"
```

### Create and publish immediately

```bash
python cli/wrs.py page build \
  --file pages/home.html \
  --css pages-css/home.css \
  --slug home \
  --title "Home" \
  --publish
```

### Update HTML and CSS

```bash
python cli/wrs.py page update --file pages/home.html --css pages-css/home.css --slug home
```

### Update only CSS

```bash
python cli/wrs.py page update-css --slug home --css pages-css/home.css
```

### Pull live HTML back to local

```bash
python cli/wrs.py page get --slug home
python cli/wrs.py pull --all-pages
```

### Compare local vs live

```bash
python cli/wrs.py page diff --slug home --file pages/home.html
```

### List WRS-managed pages

```bash
python cli/wrs.py page list
```

### List all pages (including unmanaged)

```bash
python cli/wrs.py page list --all
```

Shows all WordPress pages with their builder type, managed status, and whether they are the static front page.

### Publish a draft

```bash
python cli/wrs.py page publish --slug home
```

### Clone a page

```bash
python cli/wrs.py page clone --slug home --new-slug home-v2
```

### Set featured image

```bash
python cli/wrs.py page set-image --slug home --media-id 42
```

### Set SEO meta

```bash
python cli/wrs.py page set-meta --slug home --title "SEO Title" --description "SEO description"
```

### Delete a page

```bash
python cli/wrs.py page delete --slug home
```

---

## Inspecting Any Page

### Inspect by slug

```bash
python cli/wrs.py page inspect --slug home-2
```

### Inspect by page ID

```bash
python cli/wrs.py page inspect --id 1167
```

### Inspect the static front page

```bash
python cli/wrs.py page inspect --front
```

The inspection report shows: page ID, slug, title, status, whether it is the front page, the front-page URL, whether it is WRS-managed, which builder it uses (`elementor` or `none`), WRS source lengths, and the live page URL.

This is the right first command when working with a page that was not created by WRS.

---

## Adopting an Existing Page

Before running content edits on an existing unmanaged page you must adopt it. Adoption is explicit and cannot be reversed automatically — it is a deliberate ownership decision.

```bash
python cli/wrs.py page adopt --slug home-2
python cli/wrs.py page adopt --id 1167
```

What adoption does:

- Sets `_wrs_managed = 1` on the page
- Sets `_wrs_page_mode` to `elementor` or `html` based on what the page actually uses
- For HTML pages only: seeds `_wrs_source_html` from `post_content` if the field is currently empty
- For Elementor pages: does **not** touch any builder data — only records ownership

After adoption the page appears in `page list` and checkpoints are taken before further edits.

---

## CSS Overrides

To inject a CSS override into any page — including Elementor pages — without adopting it or touching its content:

```bash
python cli/wrs.py page css-override --slug home-2 --css overrides/welcome-color.css
```

The CSS is injected via `wp_head` at render time. It does not affect Elementor data, post content, or the page template. This is the fastest safe path to make visual changes on a live Elementor page.

To remove the override, push an empty CSS file or use `page update-css` with an empty file.

---

## Elementor Pages

### Inspect to confirm it is an Elementor page

```bash
python cli/wrs.py page inspect --front
```

Look for `builder = elementor` in the output.

### Download the Elementor JSON data

```bash
python cli/wrs.py page elementor-get --slug home-2
python cli/wrs.py page elementor-get --id 1167
python cli/wrs.py page elementor-get --slug home-2 --output elementor/home-2.json
```

This saves a JSON file containing `elementor_data` (the widget tree) and `page_settings`. The file is the local source of truth for the Elementor page.

### Upload modified Elementor JSON data

```bash
python cli/wrs.py page elementor-set --slug home-2 --file elementor/home-2.json
```

This writes the Elementor data back to the live page. It:

- Updates `_elementor_data` in WordPress post meta
- Clears Elementor's generated CSS cache so styles regenerate on the next page view
- Does **not** overwrite `post_content` or touch the page template
- Creates a checkpoint before writing so you can roll back if needed

### Notes on Elementor safety

- Never run `page build` or `page update` on a page with `builder = elementor`. Those commands write HTML content and would overwrite the Elementor structure.
- Use `page adopt` before `elementor-set` if you want the page tracked in WRS.
- Use `page css-override` for visual changes that do not require editing the widget tree.

---

## AI-Assisted Page Operations

WRS can call a local AI CLI command configured as `ai_cli_command` in `local.config.json`.

The AI command should:
- read a prompt from stdin
- return either raw HTML or JSON with `html` and `css` keys

Set the command during the wizard (step 7) or leave it blank and set it later.

### Generate a new page from a prompt

```bash
python cli/wrs.py page generate --slug landing --prompt "Landing page for a fitness app"
```

### Generate and review locally before deploying

```bash
python cli/wrs.py page generate --slug landing --prompt "Landing page for a fitness app" --review
```

### AI-update an existing page

```bash
python cli/wrs.py page ai-update --slug landing --instruction "Add a testimonials section and improve the CTA"
```

In `--review` mode WRS writes generated files locally so a human or AI can inspect them before any deployment happens.

---

## Multi-Site

### List configured sites

```bash
python cli/wrs.py sites
```

### Switch active site

```bash
python cli/wrs.py use example.com
```

All commands use the active site by default. Pass `--site <name>` to override.

---

## Deploy Flow

### Deploy all changed pages

```bash
python cli/wrs.py deploy --only pages
```

### Dry run

```bash
python cli/wrs.py deploy --dry-run
```

### Deploy a single file

```bash
python cli/wrs.py deploy --file pages/home.html
```

---

## Rollback, Checkpoints, and Journals

These three features are the safety core of WRS.

### Journal

```bash
python cli/wrs.py journal list
python cli/wrs.py journal show --op-id <id>
python cli/wrs.py journal tail
python cli/wrs.py journal export --output journal.json
```

### Checkpoints

WRS creates a checkpoint before every write operation. For Elementor pages, the checkpoint includes the full `elementor_data` so a rollback restores the builder content, not just WRS meta.

```bash
python cli/wrs.py checkpoint list
python cli/wrs.py checkpoint show --checkpoint-id <id>
python cli/wrs.py checkpoint clear
```

### Rollback

```bash
python cli/wrs.py rollback --last --dry-run
python cli/wrs.py rollback --last
python cli/wrs.py rollback --op-id <id>
python cli/wrs.py rollback --checkpoint-id <id>
```

---

## Circuit Breaker

The circuit breaker stops bad write loops automatically.

| State | Meaning |
|-------|---------|
| `CLOSED` | Normal — writes are allowed |
| `HALF-OPEN` | Warning threshold reached |
| `OPEN` | Writes blocked until root cause is fixed and breaker is reset |

```bash
python cli/wrs.py circuit-breaker status
python cli/wrs.py circuit-breaker history
python cli/wrs.py circuit-breaker test
python cli/wrs.py circuit-breaker reset
```

If the breaker is open: inspect failures → fix root cause → then reset. Do not retry writes blindly.

---

## Server Diagnostics

```bash
python cli/wrs.py server health
python cli/wrs.py server errors
python cli/wrs.py server db-status
python cli/wrs.py server file-check
python cli/wrs.py server php-info
```

---

## Config Maintenance

### Rotate the secret token

```bash
python setup/wizard.py --rotate-token --site example.com
```

### Update allowlisted IPs

```bash
python setup/wizard.py --only ips --site example.com
```

### Update enabled modules

```bash
python setup/wizard.py --only modules --site example.com
```

### Upgrade config schema

```bash
python setup/wizard.py --upgrade --site example.com
```

### Add another site

```bash
python setup/wizard.py --new-site
python cli/wrs.py sites
python cli/wrs.py use example.com
```

---

## CSS Modes

| Mode | Behaviour |
|------|-----------|
| `inline` | CSS is stored in page meta and injected into `<head>` at render time. Recommended — simplest setup. |
| `enqueue` | CSS is written to a generated file on the server and loaded with `wp_enqueue_style`. |

Choose the mode at setup time. It can be changed per-site via the wizard or the WordPress admin panel.

---

## Security Model

Every request through WRS is protected by multiple layers:

```text
1. HTTPS only                         — rejected at the plugin level if not SSL
2. IP allowlist                       — optional per-site IP restriction
3. bcrypt token verification          — server stores only the hash, never plaintext
4. HMAC-SHA256 request signing        — covers route + timestamp + payload
5. Timestamp replay window (30 s)     — stale requests are rejected
6. Replay cache                       — same signature cannot be used twice
7. Rate limiting (20 req/min)         — per-IP
8. Master enable switch               — single toggle disables the entire API
```

The pairing code adds a separate pre-authentication path:

```text
9. One-time nonce (30-min expiry)     — generated by WP admin, consumed once by the CLI
10. Pairing rate limit (5 per 15 min) — per-IP, protects the pair endpoint
```

Local token storage:

```text
~/.wrs/sites/<site>/local.config.json   plaintext token — keep out of version control
```

Server token storage:

```text
plugin.config.json → token_hash        bcrypt only, never plaintext
```

---

## Troubleshooting

### Preflight fails

Run preflight first to get a specific diagnosis:

```bash
python cli/wrs.py preflight
```

Each failing check shows the exact reason and a remediation hint.

### `status` fails

```bash
python cli/wrs.py server health
python cli/wrs.py server file-check
python cli/wrs.py config check
```

Common causes:
- plugin not activated in WordPress
- `wp-config.php` missing the `WRS_CONFIG_PATH` line
- wrong token — rotate with `python setup/wizard.py --rotate-token`
- your IP is not allowlisted — adjust in WordPress → WP Remote Shell → Access Control
- site URL mismatch between local config and WordPress

### A write failed

```bash
python cli/wrs.py journal list
python cli/wrs.py checkpoint list
python cli/wrs.py rollback --last --dry-run
```

Inspect the last operation before retrying.

### Circuit breaker is open

Do not keep retrying writes.

```bash
python cli/wrs.py circuit-breaker history
python cli/wrs.py journal list
python cli/wrs.py checkpoint list
```

Fix the root cause, then:

```bash
python cli/wrs.py circuit-breaker reset
```

### Lost access from a new machine

Use the pairing flow — see [Connecting From A New Machine](#connecting-from-a-new-machine-pairing) above.

### Connection working but want to decommission

```bash
python cli/wrs.py disconnect --revoke
```

This clears the server token and disables the API. Re-run the wizard or use pairing to reconnect.

### Elementor page not updating after elementor-set

Elementor's CSS is regenerated on the next page view after the cache is cleared. If styles still look stale, hard-reload the browser (Ctrl+Shift+R / Cmd+Shift+R) or purge any active page-caching plugin.

---

## Templates

Starter templates are included for:

- landing page
- blog post
- login / register
- dashboard
- contact
- product / shop
- coming soon

Use them as starting points for manual editing or AI generation.

---

## AI Agent Guide

If an AI coding or terminal agent is operating this repo, read these first:

- [AGENTS.md](AGENTS.md) — constraints, session flow, telemetry interpretation
- [docs/AI-WORKFLOW.md](docs/AI-WORKFLOW.md)
- [docs/ai-cli-playbook.md](docs/ai-cli-playbook.md)
- [docs/CLI-REFERENCE.md](docs/CLI-REFERENCE.md)

## Additional Documentation

- [docs/README.md](docs/README.md) — quick start
- [docs/INSTALL.md](docs/INSTALL.md) — install guide
- [docs/SECURITY.md](docs/SECURITY.md) — security detail
- [docs/FAULT-TOLERANCE.md](docs/FAULT-TOLERANCE.md)
- [docs/RECOVERY.md](docs/RECOVERY.md)

---

## Short Version

```text
edit local files
   -> preflight
   -> reconcile --all
   -> page build or page update
   -> inspect telemetry
   -> publish if desired
   -> rollback if needed
```

Lost access from a different machine? `python cli/wrs.py pair <code>` — get the code from WordPress admin.

Want to disconnect? `python cli/wrs.py disconnect` (add `--revoke` to also clear the server token).

Plugin version: **0.2.0**
