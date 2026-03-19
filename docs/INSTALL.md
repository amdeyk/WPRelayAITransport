# Installation

## Local setup

1. `pip install -r requirements.txt`
2. `python setup/wizard.py`
3. Review the generated files in `setup/output/<site>/`
4. Confirm that `wp-remote-shell.zip` and `wp-config-line.txt` exist in that folder

`<site>` is the folder name derived from the WordPress site URL you entered in the wizard. For example, `https://example.com` produces `setup/output/example.com/`.

The wizard is guided. It validates the site URL, explains the recommended choices for page mode and CSS mode, treats the AI CLI command as optional, recommends the safe module set, and shows a review screen before any files are written.

## WordPress setup

1. In WordPress Admin, go to `Plugins` > `Add New` > `Upload Plugin`
2. Upload `setup/output/<site>/wp-remote-shell.zip`
3. Activate the plugin
4. Open `setup/output/<site>/wp-config-line.txt`
5. Copy its single `define('WRS_CONFIG_PATH', ...)` line into `wp-config.php`

After activation, WordPress should show a top-level `WP Remote Shell` item in the left admin sidebar. The Plugins screen also includes a `Settings` link for the plugin.

The first-run default is `Allow all IPs during setup` so a beginner can connect without already knowing their public IP. After the connection works, narrow the allowlist with `python setup/wizard.py --only ips --site <site>`.

Upload only the `.zip` file. Do not upload the whole folder and do not upload `plugin.config.json`.

## Deploy the server config

```bash
python cli/wrs.py setup deploy-config
```

## Run the preflight check

After deploying the config, run the full preflight before doing anything else:

```bash
python cli/wrs.py preflight
```

The preflight verifies eight things in sequence:

| Check | What it verifies |
|-------|-----------------|
| Local config | Required fields present in `~/.wrs/sites/<site>/local.config.json` |
| Site reachable | The WordPress site URL responds over HTTP |
| Plugin ping (auth) | An authenticated request reaches the plugin and the token is valid |
| Server health | Server reports `status=ok` |
| Server config file | `plugin.config.json` exists at the expected server path |
| Circuit breaker | CLOSED — writes are allowed |
| Content module | The content module is enabled |
| PHP environment | PHP version, memory limit, max execution time (informational) |

All eight checks must pass before operating. Any failure prints the exact reason and the remediation command to run.

## Verify (quick alternative)

If you want a quick one-liner check:

```bash
python cli/wrs.py status
```

If the plugin is reachable and the token/config are correct, the CLI prints server metadata and module status.

## Pairing a new machine (no re-install needed)

If the plugin is already installed and you are on a different machine:

1. In WordPress Admin → WP Remote Shell, click **Generate CLI Pairing Code**
2. Run: `python cli/wrs.py pair <hex-code>`
3. Run: `python cli/wrs.py preflight`

## Maintenance

```bash
python setup/wizard.py --rotate-token --site example.com
python setup/wizard.py --only ips --site example.com
python setup/wizard.py --only modules --site example.com
python setup/wizard.py --upgrade --site example.com
```
