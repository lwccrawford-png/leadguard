#!/usr/bin/env bash
# Nightly backup of every client's SQLite data. Run via cron on the server, e.g.:
#   0 3 * * * /opt/leadguard/ops/deploy/backup.sh >> /var/log/leadguard-backup.log 2>&1
#
# Copies each client's data directory to a dated local archive. Point BACKUP_DEST at
# off-server storage (an S3-compatible bucket mounted locally, or a synced directory)
# rather than leaving backups on the same disk as the data they protect.

set -euo pipefail

DATA_ROOT="/opt/leadguard/data"
BACKUP_DEST="${BACKUP_DEST:-/opt/leadguard/backups}"
STAMP="$(date +%Y-%m-%d)"

mkdir -p "${BACKUP_DEST}/${STAMP}"

for client_dir in "$DATA_ROOT"/*/; do
  client_id="$(basename "$client_dir")"
  tar -czf "${BACKUP_DEST}/${STAMP}/${client_id}.tar.gz" -C "$DATA_ROOT" "$client_id"
done

# Keep 30 days of local backups; anything older assumes it's already synced off-server.
find "$BACKUP_DEST" -maxdepth 1 -type d -mtime +30 -exec rm -rf {} +

echo "Backed up $(ls "$DATA_ROOT" | wc -l) client(s) to ${BACKUP_DEST}/${STAMP}"
