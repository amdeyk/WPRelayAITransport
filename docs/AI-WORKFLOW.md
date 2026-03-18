# AI Workflow

The primary AI-facing operator guide for this repository is [AGENTS.md](/D:/wprelay/AGENTS.md).
The short command-oriented companion is [docs/ai-cli-playbook.md](/D:/wprelay/docs/ai-cli-playbook.md).

Use it as the authoritative instructions for:

- preflight checks
- safe write workflows
- page build/update/generate patterns
- rollback and checkpoint recovery
- telemetry interpretation
- implemented versus not-yet-implemented modules

Minimal session checklist:

1. `python cli/wrs.py status`
2. `python cli/wrs.py config check`
3. `python cli/wrs.py circuit-breaker status`
4. `python cli/wrs.py reconcile --all`

If any write fails, inspect journal and checkpoints before retrying.
