#!/bin/bash
# HAYAT v2.0 — Automated Backup Script
# Run via cron: 0 2 * * * /app/scripts/backup/backup.sh

set -euo pipefail

BACKUP_DIR="/backups/hayat"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=30
S3_BUCKET="${HAYAT_S3_BACKUP_BUCKET:-hayat-backups}"

mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting HAYAT backup..."

# PostgreSQL backup
echo "Backing up PostgreSQL..."
pg_dump \
  --host="${POSTGRES_HOST:-localhost}" \
  --port="${POSTGRES_PORT:-5432}" \
  --username="${POSTGRES_USER:-hayat}" \
  --dbname="${POSTGRES_DB:-hayat_db}" \
  --format=custom \
  --file="$BACKUP_DIR/postgres_$TIMESTAMP.dump"

# Neo4j backup
echo "Backing up Neo4j..."
neo4j-admin database dump neo4j \
  --to-path="$BACKUP_DIR/neo4j_$TIMESTAMP.dump"

# OpenSearch snapshot
echo "Creating OpenSearch snapshot..."
curl -X PUT "${OPENSEARCH_HOST:-localhost:9200}/_snapshot/hayat_backup/snapshot_$TIMESTAMP?wait_for_completion=true" \
  -H 'Content-Type: application/json' \
  -d '{
    "indices": "hayat-*",
    "ignore_unavailable": true,
    "include_global_state": false
  }'

# MinIO bucket sync
echo "Syncing MinIO to S3..."
mc mirror \
  "${MINIO_ALIAS:-hayat}/${MINIO_BUCKET:-hayat-documents}" \
  "s3/$S3_BUCKET/documents/$TIMESTAMP/"

# Compress and encrypt
echo "Compressing backups..."
tar -czf "$BACKUP_DIR/hayat_backup_$TIMESTAMP.tar.gz" \
  -C "$BACKUP_DIR" \
  "postgres_$TIMESTAMP.dump" \
  "neo4j_$TIMESTAMP.dump"

# Encrypt with GPG (key must be pre-imported)
if command -v gpg &> /dev/null && [ -f /secrets/backup-public.key ]; then
  gpg --encrypt --recipient-file /secrets/backup-public.key \
    --output "$BACKUP_DIR/hayat_backup_$TIMESTAMP.tar.gz.gpg" \
    "$BACKUP_DIR/hayat_backup_$TIMESTAMP.tar.gz"
  rm "$BACKUP_DIR/hayat_backup_$TIMESTAMP.tar.gz"
fi

# Upload to S3
echo "Uploading to S3..."
aws s3 cp "$BACKUP_DIR/hayat_backup_$TIMESTAMP.tar.gz*" "s3://$S3_BUCKET/backups/"

# Cleanup old local backups
find "$BACKUP_DIR" -name "*.dump" -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR" -name "*.tar.gz*" -mtime +$RETENTION_DAYS -delete

# Cleanup old S3 backups
aws s3 ls "s3://$S3_BUCKET/backups/" | \
  awk '{print $4}' | \
  sort -r | \
  tail -n +31 | \
  xargs -I {} aws s3 rm "s3://$S3_BUCKET/backups/{}"

echo "[$(date)] Backup completed successfully."
