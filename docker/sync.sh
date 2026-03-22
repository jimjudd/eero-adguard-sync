#!/bin/sh
set -eu

timestamp() {
  date '+%Y-%m-%d %H:%M:%S'
}

echo "[$(timestamp)] [eag-sync] Sync run started"

eag-sync sync -y

echo "[$(timestamp)] [eag-sync] Sync run finished successfully"
