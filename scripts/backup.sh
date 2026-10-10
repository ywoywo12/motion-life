#!/usr/bin/env bash
# Backup: PostgreSQL custom-format dump + uploaded attachments, with SHA-256 checksums and retention.
# Usage: DATABASE_URL=postgresql://... BACKUP_DIR=/var/backups/motionlife ./scripts/backup.sh
# Schedule daily (cron/systemd timer) and copy BACKUP_DIR off-site (encrypted). See docs/backup-restore.md.
set -euo pipefail
: "${DATABASE_URL:?DATABASE_URL is required}"
BACKUP_DIR="${BACKUP_DIR:-./var/backups}"
UPLOAD_DIR="${UPLOAD_DIR:-./var/uploads}"
KEEP_DAYS="${KEEP_DAYS:-30}"
TS="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$BACKUP_DIR"
umask 077
DB_FILE="$BACKUP_DIR/motionlife-$TS.dump"
pg_dump --format=custom --no-owner --no-privileges --file "$DB_FILE" "$DATABASE_URL"
if [ -d "$UPLOAD_DIR" ]; then
  tar -C "$UPLOAD_DIR" -czf "$BACKUP_DIR/uploads-$TS.tar.gz" .
fi
( cd "$BACKUP_DIR" && sha256sum "motionlife-$TS.dump" $( [ -f "uploads-$TS.tar.gz" ] && echo "uploads-$TS.tar.gz" ) > "SHA256SUMS-$TS" )
# verify the dump is readable
pg_restore --list "$DB_FILE" > /dev/null
find "$BACKUP_DIR" -type f -mtime +"$KEEP_DAYS" \( -name 'motionlife-*.dump' -o -name 'uploads-*.tar.gz' -o -name 'SHA256SUMS-*' \) -delete
echo "backup ok: $DB_FILE"
