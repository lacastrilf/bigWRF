#!/usr/bin/env bash
# Sube los wrfout de la EC2 a S3 (zona raw), sin transformarlos.
# /data/wrf/<esquema>/  ->  s3://<bucket>/raw/wrf/esquema=<esquema>/
set -euo pipefail

BUCKET="${BUCKET:-p2-derecho-104744115873}"
SRC="${SRC:-/data/wrf}"
LOG=/var/log/ingest_wrf.log

exec 9>/tmp/ingest_wrf.lock
flock -n 9 || { echo "$(date -u +%FT%TZ) ya hay una ejecucion en curso" >> "$LOG"; exit 0; }

for dir in "$SRC"/*/; do
  [ -d "$dir" ] || continue
  esquema=$(basename "$dir")
  echo "$(date -u +%FT%TZ) sync $esquema" >> "$LOG"
  aws s3 sync "$dir" "s3://$BUCKET/raw/wrf/esquema=$esquema/" --region us-east-1 --only-show-errors >> "$LOG" 2>&1
done
echo "$(date -u +%FT%TZ) fin" >> "$LOG"
