# HAYAT v2.0 — Disaster Recovery Runbook

## RTO: 4 hours | RPO: 1 hour

### Scenario 1: PostgreSQL Failure
```bash
# 1. Identify latest backup
LATEST=$(aws s3 ls s3://hayat-backups/backups/ | sort | tail -1 | awk '{print $4}')

# 2. Download and restore
aws s3 cp "s3://hayat-backups/backups/$LATEST" /tmp/
pg_restore --host=$POSTGRES_HOST --username=$POSTGRES_USER \
  --dbname=$POSTGRES_DB --clean --if-exists /tmp/$LATEST

# 3. Verify
psql -c "SELECT COUNT(*) FROM cases;"
```

### Scenario 2: Neo4j Failure
```bash
# Stop Neo4j
kubectl scale deployment hayat-neo4j --replicas=0

# Restore from dump
neo4j-admin database load neo4j --from-path=/backups/neo4j_latest.dump

# Restart
kubectl scale deployment hayat-neo4j --replicas=1
```

### Scenario 3: Complete Region Failure
1. Activate standby region (us-west-2)
2. Update DNS to point to standby load balancer
3. Verify data consistency across regions
4. Notify stakeholders via PagerDuty

### Scenario 4: Data Corruption
1. Stop all writes immediately
2. Identify corruption point from audit logs
3. Restore to last known good backup
4. Replay transactions from WAL if possible
5. Verify integrity with checksums

### Contact Escalation
- L1: On-call engineer (15 min)
- L2: Platform lead (30 min)
- L3: CTO (1 hour)
- L4: External DR consultant (2 hours)
