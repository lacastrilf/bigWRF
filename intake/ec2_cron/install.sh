#!/usr/bin/env bash
# Instala cron, el script de ingesta y la tarea horaria. Ejecutar como root.
set -euo pipefail
BUCKET="${BUCKET:-p2-derecho-104744115873}"

dnf install -y cronie >/dev/null
systemctl enable --now crond

mkdir -p /opt/p2
aws s3 cp "s3://$BUCKET/scripts/ec2/ingest_wrf.sh" /opt/p2/ingest_wrf.sh --region us-east-1
chmod +x /opt/p2/ingest_wrf.sh
touch /var/log/ingest_wrf.log && chown ec2-user /var/log/ingest_wrf.log

# Cada hora, al minuto 0
echo "0 * * * * ec2-user BUCKET=$BUCKET /opt/p2/ingest_wrf.sh" > /etc/cron.d/ingest-wrf
chmod 644 /etc/cron.d/ingest-wrf
echo "instalado:"; cat /etc/cron.d/ingest-wrf
