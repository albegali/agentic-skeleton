# Migrations

`<from>-<to>.py`: run by the upgrade (`make sync-skeleton`) in the project root when it moves across that range,
oldest first, after the workflow files are updated. Use them for changes that files alone cannot carry: renamed
artifact sections, moved folders, new required fields. Stdlib only, idempotent, print one line of what changed.
