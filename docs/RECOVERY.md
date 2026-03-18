# Recovery

If a content operation fails after a checkpoint is created:

1. Inspect the journal entry in `~/.wrs/sites/<site>/journal.ndjson`
2. Find the checkpoint ID in the operation record
3. Use the matching server rollback endpoint or restore the local checkpoint copy manually
4. Re-run `python cli/wrs.py status`

