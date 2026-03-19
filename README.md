# WP Remote Shell

WP Remote Shell (WRS) is a CLI-first WordPress operations system.

It lets you build and update WordPress pages from local files, then push those changes through a signed API bridge instead of using WordPress Admin for day-to-day editing.

Today, this repository is strongest in one complete vertical slice:

- setup and packaging
- authenticated transport
- journaling and checkpoints
- rollback support
- page build / update / publish workflows
- AI-assisted page generation and update

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

- your HTML/CSS lives locally
- your changes can be versioned in git
- each write operation is tracked
- a checkpoint is created before changes
- rollback is available if a write goes wrong
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

Implemented now:

- setup wizard and config generation
- plugin ZIP packaging
- per-site local and server config handling
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
  - generate
  - ai-update
- server diagnostics:
  - health
  - errors
  - db-status
  - file-check
  - php-info
- page-only deploy flow
- pull and pull-all-pages
- page reconciliation

Not fully implemented yet:

- media module
- database/migrations module
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
|   `-- modules/                 page, server, setup, rollback, reconcile, etc.
|-- plugin/
|   |-- wp-remote-shell.php      plugin bootstrap
|   |-- includes/                auth, router, telemetry, checkpoint helpers
|   |-- modules/                 WordPress capability modules
|   |-- schema/                  SQL install/uninstall definitions
|   `-- templates/               canvas template
|-- setup/
|   |-- wizard.py                interactive setup + maintenance
|   |-- build_config.py          config creation helpers
|   `-- build_plugin.py          plugin ZIP packaging
|-- config/
|   |-- local.config.template.json
|   `-- plugin.config.template.json
|-- templates/                   starter HTML/CSS page templates
`-- docs/                        install, CLI, security, recovery, AI docs
```

## The Main Idea

Think of WRS like this:

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

## First-Time Installation For A Beginner

This section assumes:

- you have Python installed
- you have a WordPress site already running
- you can log in to WordPress Admin
- you can edit `wp-config.php` on the server once

### Step 1: Get the repository

If you already have the repo locally, skip this.

```bash
git clone <your-repo-url>
cd wp-remote-shell
```

### Step 2: Install Python dependencies

```bash
pip install -r requirements.txt
```

If `pip` is not found, try:

```bash
python -m pip install -r requirements.txt
```

### Step 3: Run the setup wizard

```bash
python setup/wizard.py
```

The wizard will ask for:

- your WordPress site URL
- local project path
- allowlisted IPs
- token generation
- page mode
- CSS mode
- default status
- AI CLI command
- circuit-breaker reset PIN
- which modules to enable

### Step 4: What the wizard creates

After the wizard runs, WRS creates:

```text
~/.wrs/sites/<site>/local.config.json      local plaintext config
~/.wrs/sites/<site>/plugin.config.json     server config payload
setup/output/<site>/wp-remote-shell.zip    plugin ZIP to upload
setup/output/<site>/wp-config-line.txt     line to paste into wp-config.php
<project_path>/pages/                      your local page HTML files
<project_path>/pages-css/                  your local CSS files
```

`<site>` is the site folder name that WRS derives from your WordPress URL.

Example:

- if your site URL is `https://example.com`, the output folder is `setup/output/example.com/`
- if your site URL is `https://clientsite.com`, the output folder is `setup/output/clientsite.com/`

Before you continue, open that folder and confirm that these two files exist:

- `wp-remote-shell.zip`
- `wp-config-line.txt`

If you do not see them, the wizard did not finish successfully. Run `python setup/wizard.py` again and note the site URL you enter, because that determines the `<site>` folder name.

### Step 5: Upload the plugin in WordPress

This is one of the very few browser steps.

In WordPress Admin:

1. Log in to your WordPress Admin dashboard.
2. Go to `Plugins`.
3. Click `Add New Plugin` or `Add New`.
4. Click `Upload Plugin` near the top of the page.
5. Click `Choose File`.
6. Select `setup/output/<site>/wp-remote-shell.zip` from your local project folder.
7. Click `Install Now`.
8. After WordPress finishes uploading and installing it, click `Activate Plugin`.

After activation, you should see a top-level `WP Remote Shell` menu in the left admin sidebar. The plugin row in `Plugins` also gets a `Settings` link that opens the same page.

The admin page is an editable settings screen, not a raw JSON viewer. New builds default to `Allow all IPs during setup` so the first connection works for novice users, and the allowlist can be tightened later from inside WordPress.

Important:

- upload the `.zip` file itself, not the whole `setup/output/<site>/` folder
- do not unzip the file manually before uploading
- `plugin.config.json` is not the file you upload in WordPress

Example on this repo:

```text
setup/output/example.com/wp-remote-shell.zip
```

### Step 6: Add the WRS config path to `wp-config.php`

Open the generated file:

```text
setup/output/<site>/wp-config-line.txt
```

It contains a line like:

```php
define('WRS_CONFIG_PATH', dirname(__FILE__) . '/wp-content/uploads/wrs/plugin.config.json');
```

Copy that one line and add it to your site's `wp-config.php` file.

Good place to put it:

- above the line that says `/* That's all, stop editing! Happy publishing. */`

This tells the plugin where to load its secure runtime configuration from.

Important:

- paste the contents of `wp-config-line.txt` into `wp-config.php`
- do not paste the filename itself
- do not edit `plugin.config.json` by hand

### Step 7: Deploy the server config

Back in your terminal:

```bash
python cli/wrs.py setup deploy-config
```

This sends the generated `plugin.config.json` to the WordPress server through the authenticated WRS channel.

If this is your first time setting up a site, the order is:

1. run the wizard
2. upload and activate the plugin in WordPress
3. add the generated `WRS_CONFIG_PATH` line to `wp-config.php`
4. run `python cli/wrs.py setup deploy-config`
5. run the verification commands below

### Step 8: Verify everything works

Run:

```bash
python cli/wrs.py status
python cli/wrs.py config check
python cli/wrs.py server health
```

If these succeed, the local CLI and the WordPress plugin can talk to each other.

## The Safe Operating Pattern

Use this pattern every time:

```text
1. Check status
2. Check config
3. Check circuit breaker
4. Reconcile
5. Read live state if needed
6. Edit local files
7. Push the smallest valid change
8. Read telemetry
9. Roll back if necessary
```

The matching commands:

```bash
python cli/wrs.py status
python cli/wrs.py config check
python cli/wrs.py circuit-breaker status
python cli/wrs.py reconcile --all
```

## Your Local Project Folder

WRS creates and expects a site project folder like this:

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

For the current implementation, `pages/` and `pages-css/` are the most important directories.

## How To Create And Publish A Page

### Create local files

Example:

```text
pages/home.html
pages-css/home.css
```

### Build the page into WordPress

```bash
python cli/wrs.py page build --file pages/home.html --css pages-css/home.css --slug home --title "Home"
```

What happens internally:

```text
local files
   -> local journal PENDING
   -> server checkpoint created
   -> signed POST to plugin
   -> WordPress page created or updated
   -> telemetry returned
   -> local journal updated
   -> circuit breaker evaluated
```

### Publish the page

If you built it as draft, publish it with:

```bash
python cli/wrs.py page publish --slug home
```

Or build and publish in one step:

```bash
python cli/wrs.py page build --file pages/home.html --css pages-css/home.css --slug home --title "Home" --publish
```

## Common Page Commands

### Create a page

```bash
python cli/wrs.py page build --file pages/home.html --css pages-css/home.css --slug home --title "Home"
```

### Update HTML/CSS

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

## How AI Should Control WRS

An AI CLI should not operate WordPress by improvising browser-style behavior.

It should use this control loop:

```text
AI reads repo + AGENTS.md + AI CLI playbook
   -> runs preflight checks
   -> inspects live page state when necessary
   -> edits local files
   -> runs one WRS command
   -> reads telemetry and journal output
   -> either continues, stops, or rolls back
```

### AI preflight commands

```bash
python cli/wrs.py status
python cli/wrs.py config check
python cli/wrs.py circuit-breaker status
python cli/wrs.py reconcile --all
```

### AI write rule

For existing pages:

1. inspect live page
2. compare local file
3. edit local file
4. run `page update`
5. inspect telemetry

### AI publish rule

Do not publish by default unless the user explicitly asked for publish.

Safer default:

```bash
python cli/wrs.py page build --file pages/home.html --css pages-css/home.css --slug home --title "Home"
```

Then publish only when asked:

```bash
python cli/wrs.py page publish --slug home
```

### AI rollback rule

If a write fails:

- do not loop retries blindly
- inspect journal
- inspect checkpoints
- inspect `recovery_hint`
- use rollback if needed

Commands:

```bash
python cli/wrs.py journal list
python cli/wrs.py checkpoint list
python cli/wrs.py rollback --last --dry-run
python cli/wrs.py rollback --last
```

## AI-Assisted Page Generation

WRS can call a local AI command defined in `local.config.json` as `ai_cli_command`.

Expected AI command behavior:

- accept a prompt from stdin
- return either:
  - raw HTML
  - or JSON with `html` and `css`

### Generate a new page

```bash
python cli/wrs.py page generate --slug landing --prompt "Landing page for a fitness app"
```

### Generate but stop before deployment

```bash
python cli/wrs.py page generate --slug landing --prompt "Landing page for a fitness app" --review
```

### AI update an existing page

```bash
python cli/wrs.py page ai-update --slug landing --instruction "Add a testimonials section and improve the CTA"
```

In review mode, WRS writes generated output to local files so a human or AI can inspect them before deployment.

## Deploy Flow

Current deploy support is page-focused.

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

## Rollback, Checkpoints, And Journals

These three features are the safety core of WRS.

### Journal

The local journal tracks operations and outcomes.

```bash
python cli/wrs.py journal list
python cli/wrs.py journal show --op-id <id>
python cli/wrs.py journal tail
python cli/wrs.py journal export --output journal.json
```

### Checkpoints

Before page writes, WRS can create a checkpoint.

```bash
python cli/wrs.py checkpoint list
python cli/wrs.py checkpoint show --checkpoint-id <id>
python cli/wrs.py checkpoint clear
```

### Rollback

Rollback restores the state captured by a checkpoint.

```bash
python cli/wrs.py rollback --last --dry-run
python cli/wrs.py rollback --last
python cli/wrs.py rollback --op-id <id>
python cli/wrs.py rollback --checkpoint-id <id>
```

## Circuit Breaker

The circuit breaker exists to stop bad write loops.

States:

- `CLOSED` = normal
- `HALF-OPEN` = warning
- `OPEN` = writes should stop until the issue is understood

Commands:

```bash
python cli/wrs.py circuit-breaker status
python cli/wrs.py circuit-breaker history
python cli/wrs.py circuit-breaker test
python cli/wrs.py circuit-breaker reset
```

If the breaker is open:

1. inspect recent failures
2. inspect telemetry
3. inspect checkpoints
4. fix the root cause
5. reset only after that

## Diagnostics

Use these when the connection or server behavior is unclear:

```bash
python cli/wrs.py server health
python cli/wrs.py server errors
python cli/wrs.py server db-status
python cli/wrs.py server file-check
python cli/wrs.py server php-info
```

## Config Maintenance

These maintenance flows are handled by the wizard:

### Rotate token

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

## CSS Modes

WRS currently supports:

- `inline`
- `enqueue`

### Inline mode

CSS is stored in page meta and injected into the page output.

### Enqueue mode

CSS is written to a generated asset file on the WordPress server and loaded with `wp_enqueue_style`.

## Templates

Starter templates are included for:

- landing page
- blog post
- login
- register
- dashboard
- contact
- product
- shop
- coming soon

Use them as starting points for manual editing or AI generation.

## Security Summary

WRS protects the plugin endpoint with:

```text
1. HTTPS only
2. IP allowlist
3. bcrypt token verification
4. HMAC-SHA256 request signing
5. timestamp replay window
6. replay cache
7. rate limiting
8. master enable switch
```

Local plaintext token:

```text
~/.wrs/sites/<site>/local.config.json
```

Server token storage:

```text
bcrypt hash only, never plaintext
```

## Troubleshooting For Beginners

### `status` fails

Check:

```bash
python cli/wrs.py server health
python cli/wrs.py server file-check
python cli/wrs.py config check
```

Likely causes:

- plugin not activated
- `wp-config.php` missing `WRS_CONFIG_PATH`
- wrong token or stale config
- your IP not allowlisted
- site URL mismatch

### A write failed

Do this:

```bash
python cli/wrs.py journal list
python cli/wrs.py checkpoint list
python cli/wrs.py rollback --last --dry-run
```

Then inspect the last operation before retrying.

### Circuit breaker is open

Do not keep retrying writes.

Run:

```bash
python cli/wrs.py circuit-breaker history
python cli/wrs.py journal list
python cli/wrs.py checkpoint list
```

Fix the root cause first, then reset.

## Files AI Agents Should Read

If an AI terminal tool is operating this repo, it should read these first:

- [AGENTS.md](/D:/wprelay/AGENTS.md)
- [AI CLI Playbook](/D:/wprelay/docs/ai-cli-playbook.md)
- [AI Workflow](/D:/wprelay/docs/AI-WORKFLOW.md)
- [CLI Reference](/D:/wprelay/docs/CLI-REFERENCE.md)

## Additional Documentation

- [Quick Start](/D:/wprelay/docs/README.md)
- [Install Guide](/D:/wprelay/docs/INSTALL.md)
- [Security](/D:/wprelay/docs/SECURITY.md)
- [CLI Reference](/D:/wprelay/docs/CLI-REFERENCE.md)
- [Fault Tolerance](/D:/wprelay/docs/FAULT-TOLERANCE.md)
- [AI Workflow](/D:/wprelay/docs/AI-WORKFLOW.md)
- [Recovery](/D:/wprelay/docs/RECOVERY.md)

## Short Version

If you only remember one workflow, remember this:

```text
edit local files
   -> run status/config/reconcile
   -> page build or page update
   -> inspect telemetry
   -> publish if desired
   -> rollback if needed
```
