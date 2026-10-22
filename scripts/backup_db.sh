#!/usr/bin/env sh
# Daily Postgres dump of the «Умный друг» stack with retention. Run from the repository root via cron:
#   0 3 * * * cd /srv/umnydrug && ./scripts/backup_db.sh >> /var/log/umnydrug-backup.log 2>&1
# Restore check (do it before the first release and quarterly):
#   gunzip -c backups/umnydrug-YYYY-MM-DD.sql.gz | docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"_restore_test
set -eu

cd "$(dirname "$0")/.."
. ./.env
BACKUP_DIR=${BACKUP_DIR:-./backups}
KEEP_DAYS=${BACKUP_KEEP_DAYS:-14}
mkdir -p "$BACKUP_DIR"
stamp=$(date +%F)
target="$BACKUP_DIR/umnydrug-$stamp.sql.gz"

docker compose exec -T db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --clean --if-exists \
  | gzip -9 > "$target.tmp"
mv "$target.tmp" "$target"
chmod 600 "$target"
find "$BACKUP_DIR" -name 'umnydrug-*.sql.gz' -mtime +"$KEEP_DAYS" -delete
echo "$(date -Is) backup written: $target ($(du -h "$target" | cut -f1))"
# Children's data: keep the backup directory encrypted at rest (e.g. an encrypted volume) and off-site copies encrypted too.
