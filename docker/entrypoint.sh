#!/bin/sh
set -eu

mkdir -p "${EAG_DATA_DIR:-/data}"

echo "[eag-sync] Starting container"
echo "[eag-sync] Data directory: ${EAG_DATA_DIR:-/data}"
echo "[eag-sync] Cron schedule: ${EAG_CRON_SCHEDULE:-0 * * * *}"
echo "[eag-sync] Running initial sync before cron starts"

if /usr/src/app/sync.sh; then
  echo "[eag-sync] Initial sync completed successfully"
else
  echo "[eag-sync] Initial sync failed; not starting cron"
  exit 1
fi

echo "${EAG_CRON_SCHEDULE:-0 * * * *} /usr/src/app/sync.sh >> /proc/1/fd/1 2>> /proc/1/fd/2" | crontab -
echo "[eag-sync] Cron schedule installed"
echo "[eag-sync] Starting cron daemon"
exec "$@"
