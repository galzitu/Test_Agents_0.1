#!/bin/bash
set -euo pipefail

# Simple repo -> VM sync with backup, manifest and smoke verification.
# Usage:
#   VM_HOST=user@host VM_PATH=~/trading-agent ./deploy/sync_vm.sh

if [[ -z "${VM_HOST:-}" ]]; then
  echo "VM_HOST is required, e.g. ubuntu@34.69.63.163"
  exit 1
fi

VM_PATH="${VM_PATH:-~/trading-agent}"
BACKUP_RETENTION="${BACKUP_RETENTION:-5}"
SSH_KEY_ARG=()
if [[ -n "${SSH_KEY:-}" ]]; then
  SSH_KEY_ARG=(-i "$SSH_KEY")
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
STAMP="$(date +"%Y%m%d_%H%M%S")"
MANIFEST="$PROJECT_ROOT/logs/sync_manifest_${STAMP}.json"

mkdir -p "$PROJECT_ROOT/logs"

python3 "$SCRIPT_DIR/write_manifest.py" \
  --root "$PROJECT_ROOT" \
  --output "$MANIFEST"

ssh "${SSH_KEY_ARG[@]}" "$VM_HOST" "
  mkdir -p $VM_PATH/backups
  mkdir -p $VM_PATH/backups/release_$STAMP
  if [ -d $VM_PATH/agent ]; then cp -R $VM_PATH/agent $VM_PATH/backups/release_$STAMP/; fi
  if [ -d $VM_PATH/strategies_config ]; then cp -R $VM_PATH/strategies_config $VM_PATH/backups/release_$STAMP/; fi
  if [ -f $VM_PATH/requirements.txt ]; then cp $VM_PATH/requirements.txt $VM_PATH/backups/release_$STAMP/; fi
  if [ -f $VM_PATH/start.sh ]; then cp $VM_PATH/start.sh $VM_PATH/backups/release_$STAMP/; fi
  if [ -d $VM_PATH/deploy ]; then cp -R $VM_PATH/deploy $VM_PATH/backups/release_$STAMP/; fi
  ls -1dt $VM_PATH/backups/release_* 2>/dev/null | tail -n +$((BACKUP_RETENTION + 1)) | xargs -r rm -rf
"

rsync -az --delete \
  --exclude '.env' \
  --exclude 'venv' \
  --exclude '__pycache__' \
  --exclude 'logs/*.pid' \
  -e "ssh ${SSH_KEY:+-i $SSH_KEY}" \
  "$PROJECT_ROOT/" "$VM_HOST:$VM_PATH/"

scp "${SSH_KEY_ARG[@]}" "$MANIFEST" "$VM_HOST:$VM_PATH/logs/latest_sync_manifest.json"

ssh "${SSH_KEY_ARG[@]}" "$VM_HOST" "
  cd $VM_PATH &&
  python3 -m compileall agent >/dev/null &&
  test -f logs/latest_sync_manifest.json &&
  if [ -x deploy/verify_vm.sh ]; then bash deploy/verify_vm.sh; fi
"

echo "Sync complete."
echo "Manifest: $MANIFEST"
echo "Backup retention: $BACKUP_RETENTION"
