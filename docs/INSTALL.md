# Installation

## Local setup

1. `pip install -r requirements.txt`
2. `python setup/wizard.py`
3. Review the generated files in `setup/output/<site>/`
4. Confirm that `wp-remote-shell.zip` and `wp-config-line.txt` exist in that folder

`<site>` is the folder name derived from the WordPress site URL you entered in the wizard. For example, `https://example.com` produces `setup/output/example.com/`.

## WordPress setup

1. In WordPress Admin, go to `Plugins` > `Add New` > `Upload Plugin`
2. Upload `setup/output/<site>/wp-remote-shell.zip`
3. Activate the plugin
4. Open `setup/output/<site>/wp-config-line.txt`
5. Copy its single `define('WRS_CONFIG_PATH', ...)` line into `wp-config.php`

Upload only the `.zip` file. Do not upload the whole folder and do not upload `plugin.config.json`.

## Verify

Run:

```bash
python cli/wrs.py status
```

If the plugin is reachable and the token/config are correct, the CLI prints server metadata and module status.

## Maintenance

```bash
python setup/wizard.py --rotate-token --site example.com
python setup/wizard.py --only ips --site example.com
python setup/wizard.py --only modules --site example.com
python setup/wizard.py --upgrade --site example.com
```
