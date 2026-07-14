# HAYAT v2.0 API Documentation

## Authentication

All API requests require authentication via:
- **Bearer Token**: `Authorization: Bearer <access_token>`
- **API Key**: `X-API-Key: <api_key>` (for institutional access)

## Rate Limits

| Role | Limit | Window |
|------|-------|--------|
| Public | 30 | 60s |
| Practitioner | 200 | 60s |
| Researcher | 300 | 60s |
| Legal Editor | 500 | 60s |
| Institution | 1000 | 60s |
| Super Admin | 10000 | 60s |

## Idempotency

For POST/PUT/PATCH operations, include `Idempotency-Key: <uuid>` header
to prevent duplicate processing.

## Endpoints

### Search
- `POST /api/v1/search/` — Full-text and semantic search
- `GET /api/v1/search/facets` — Search facets for filtering
- `GET /api/v1/search/timeline` — Timeline search with aggregations

### Cases
- `GET /api/v1/cases/` — List cases with filters
- `POST /api/v1/cases/` — Create case (editor only)
- `GET /api/v1/cases/{id}` — Get case details with citation network
- `PUT /api/v1/cases/{id}` — Update case

### Statutes
- `GET /api/v1/statutes/` — List statutes
- `POST /api/v1/statutes/` — Create statute (editor only)
- `GET /api/v1/statutes/{id}` — Get statute with sections
- `POST /api/v1/statutes/{id}/sections` — Add section

### AI
- `POST /api/v1/ai/ask` — RAG-based question answering
- `POST /api/v1/ai/summarize` — Case summarization
- `POST /api/v1/ai/explain` — Statute explanation
- `POST /api/v1/ai/compare` — Case comparison
- `POST /api/v1/ai/draft` — Drafting assistance
- `POST /api/v1/ai/conflict-check` — Conflict detection

### Analytics
- `GET /api/v1/analytics/trends` — Case trends
- `GET /api/v1/analytics/citations` — Citation analytics
- `GET /api/v1/analytics/judges/{name}` — Judge analytics
- `GET /api/v1/analytics/courts` — Court performance

### Practice Tools
- `POST /api/v1/practice/deadlines` — Create deadline
- `GET /api/v1/practice/deadlines` — List deadlines
- `POST /api/v1/practice/time-entries` — Log billable time

## Webhooks

Subscribe to events via `POST /api/v1/webhooks/subscribe`.

Events:
- `case.created`
- `case.updated`
- `statute.amended`
- `document.processed`
- `deadline.approaching`
- `deadline.overdue`

Webhook payloads are signed with HMAC-SHA256. Verify using `X-HAYAT-Signature` header.

## SDK

```python
from hayat_sdk import HAYATClient

client = HAYATClient(api_key="your-key")

# Search
cases = client.search_cases("mandatory injunction", area_of_law="Civil")

# Get case with citation network
case = client.get_case("case-id-123")
network = client.get_case_citation_network("case-id-123", depth=2)

# AI assistance
answer = client.ask("What are the requirements for a mandatory injunction?")
summary = client.summarize_case("case-id-123", style="practitioner")

# Analytics
trends = client.get_case_trends(area_of_law="Civil")
```

## Error Codes

| Code | Meaning |
|------|---------|
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden (insufficient permissions) |
| 404 | Not Found |
| 409 | Conflict (duplicate) |
| 415 | Unsupported Media Type |
| 429 | Rate Limit Exceeded |
| 500 | Internal Server Error |
| 503 | Service Unavailable (health check failed) |
