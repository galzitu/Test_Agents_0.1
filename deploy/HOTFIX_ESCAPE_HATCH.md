# Hotfix Escape Hatch

Use this only for production/runtime emergencies on the VM.

## Allowed flow
1. SSH to the VM.
2. Record the issue, timestamp, and changed files in `logs/hotfix_history.log`.
3. Copy the affected file to `backups/hotfix_<timestamp>/`.
4. Apply the minimum safe change.
5. Restart only the affected service.
6. Verify with a smoke check.
7. Backport the exact fix into the repo before the next normal sync.

## Important
- The repo is not auto-linked to the VM by itself.
- Normal repo -> VM updates happen only when `deploy/sync_vm.sh` is run with `VM_HOST` and SSH access.

## Required log format
```text
YYYY-MM-DDTHH:MM:SSZ | file=agent/... | reason=... | service=trading-agent | by=manual-hotfix
```

## Forbidden
- Silent fixes without logging
- Editing risk rules on the VM
- Leaving the VM ahead of the repo after the emergency passes
