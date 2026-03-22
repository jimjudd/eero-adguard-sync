#!/bin/sh
set -eu

mkdir -p "${EAG_DATA_DIR:-/data}"
echo "${EAG_CRON_SCHEDULE:-0 * * * *} /usr/src/app/sync.sh >> /proc/1/fd/1 2>> /proc/1/fd/2" | crontab -
exec "$@"
