# Installation

## Local setup

1. `pip install -r requirements.txt`
2. `python setup/wizard.py`
3. Review the generated files in `setup/output/<site>/`

## WordPress setup

1. Upload `wp-remote-shell.zip`
2. Activate the plugin
3. Add the generated `WRS_CONFIG_PATH` define to `wp-config.php`

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
