#!/usr/bin/env bash
# Restore a dump into an EMPTY target database, then print row counts for verification.
# Usage: TARGET_DATABASE_URL=postgresql://.../motionlife_restore ./scripts/restore.sh var/backups/motionlife-XXXX.dump [uploads.tar.gz] [upload_dir]
# Restore into a separate database first, verify, then switch the application's DATABASE_URL.
set -euo pipefail
DUMP="${1:?dump file required}"
: "${TARGET_DATABASE_URL:?TARGET_DATABASE_URL is required}"
SUMS="$(dirname "$DUMP")/SHA256SUMS-$(basename "$DUMP" .dump | sed 's/^motionlife-//')"
if [ -f "$SUMS" ]; then ( cd "$(dirname "$DUMP")" && sha256sum --check --ignore-missing "$(basename "$SUMS")" ); fi
existing=$(psql "$TARGET_DATABASE_URL" -tAc "select count(*) from information_schema.tables where table_schema='public'")
if [ "$existing" != "0" ] && [ "${FORCE:-0}" != "1" ]; then
  echo "target database is not empty ($existing tables). Refusing. Set FORCE=1 only if you are sure." >&2
  exit 1
fi
pg_restore --no-owner --no-privileges --exit-on-error --dbname "$TARGET_DATABASE_URL" "$DUMP"
if [ "${2:-}" != "" ]; then mkdir -p "${3:?upload_dir required}"; tar -C "$3" -xzf "$2"; fi
psql "$TARGET_DATABASE_URL" -c "select 'patients' t, count(*) from patients union all select 'answers', count(*) from answers
  union all select 'plan_versions', count(*) from plan_versions union all select 'sessions', count(*) from sessions
  union all select 'audit_events', count(*) from audit_events"
echo "restore ok"
