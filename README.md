# WP Remote Shell

WP Remote Shell (WRS) is a CLI-first WordPress operations system.

It lets you build and update WordPress pages from local files and push those changes through a signed API bridge instead of using the WordPress Admin for day-to-day editing.

Today this repository is strongest in one complete vertical slice:

- setup and packaging
- authenticated transport
- journaling and checkpoints
- rollback support
- page build / update / publish workflows
- AI-assisted page generation and update
- CLI pairing (connect a new machine without running the full wizard)
- disconnect and server-side token revocation

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

## Architecture

```text
                         WP REMOTE SHELL
    -------------------------------------------------------------

      Local Machine                               WordPress Server
    -----------------                           -------------------

    pages/home.html
    pages-css/home.css
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
- server-side checkpoints
- rollback from checkpoints
- page operations:
  - build
  - update
  - update-css
  - get
  - diff
  - list
  - publish
  - clone
  - set-image
  - set-meta
  - delete
  - generate (AI)
  - ai-update (AI)
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
|   `-- modules/                 page, server, setup, connect, rollback, reconcile, etc.
|-- plugin/
|   |-- wp-remote-shell.php      plugin bootstrap
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

### Step 8: Verify the connection

```bash
python cli/wrs.py status
python cli/wrs.py config check
python cli/wrs.py server health
```

If all three succeed, the CLI and plugin are talking to each other.

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

Confirm the connection:

```bash
python cli/wrs.py status
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
python cli/wrs.py status
python cli/wrs.py config check
python cli/wrs.py circuit-breaker status
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
|-- partials/
|-- posts/
|-- media/
|-- migrations/
`-- wrs-manifest.json
```

For the current implementation `pages/` and `pages-css/` are the most important directories.

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

### List all WRS-managed pages

```bash
python cli/wrs.py page list
```

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

WRS creates a checkpoint before every write operation.

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
   -> status / config check / circuit-breaker check / reconcile
   -> page build or page update
   -> inspect telemetry
   -> publish if desired
   -> rollback if needed
```

Lost access from a different machine? `python cli/wrs.py pair <code>` — get the code from WordPress admin.

Want to disconnect? `python cli/wrs.py disconnect` (add `--revoke` to also clear the server token).
