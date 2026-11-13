#!/usr/bin/env bash
# Runs on a prepared deployment host, never automatically against the local dev DB.
set -euo pipefail
ARCHIVE="${1:?Pass the portal image archive from CI}"
ENV_FILE="${2:?Pass the absolute path to the server .env}"
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
[[ -f "$ARCHIVE" && -f "$ENV_FILE" ]] || { echo 'Release archive or environment file missing' >&2; exit 1; }
: "${PORTAL_IMAGE:?Set the tag nirs-portal:<CI build ID>}"
compose=(docker compose --env-file "$ENV_FILE" -p nirs-portal-prod -f "$PROJECT_ROOT/compose.production.yaml")
"${compose[@]}" config --quiet
docker load -i "$ARCHIVE"
"${compose[@]}" up -d --wait db
BACKUP_DIR="$(dirname "$ENV_FILE")/backups"
mkdir -p "$BACKUP_DIR"
umask 077
BACKUP_FILE="$BACKUP_DIR/$(date -u +%Y%m%dT%H%M%SZ)-before-migration.dump"
"${compose[@]}" exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$BACKUP_FILE"
# A failed migration stops the release before replacing the existing app.
"${compose[@]}" run --rm migrate
"${compose[@]}" up -d --wait app
printf 'Release healthy. Database backup: %s\n' "$BACKUP_FILE"
