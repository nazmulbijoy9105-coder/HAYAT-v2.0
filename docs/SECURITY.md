# HAYAT v2.0 — Security Runbook

## Incident Response

### P1: Data Breach
1. Immediately revoke all active sessions
2. Rotate JWT secret keys
3. Audit all access logs for the last 72 hours
4. Notify affected users within 24 hours (GDPR/Bangladesh DPA compliance)
5. File incident report with Bangladesh Telecommunication Regulatory Commission

### P2: API Abuse
1. Identify offending API key/user
2. Apply emergency rate limit (1 req/min)
3. Review audit logs for pattern
4. Revoke API key if malicious
5. Update WAF rules

### P3: AI Hallucination Report
1. Flag the response in database
2. Review source documents used in RAG
3. Update prompt engineering if systematic
4. Notify editorial team for manual review
5. Publish correction if published content

## Security Checklist (Monthly)

- [ ] Review all active API keys
- [ ] Check for unused user accounts
- [ ] Verify backup encryption
- [ ] Review audit logs for anomalies
- [ ] Update dependency vulnerabilities (Dependabot)
- [ ] Test disaster recovery procedure
- [ ] Review RBAC permissions
- [ ] Verify SSL certificate expiry
- [ ] Check MinIO bucket policies
- [ ] Review Neo4j access logs

## Secrets Management

All secrets managed via:
- Development: `.env` file (never committed)
- Staging: GitHub Secrets + Kubernetes Secrets
- Production: HashiCorp Vault + AWS Secrets Manager

Never hardcode secrets in source code.
