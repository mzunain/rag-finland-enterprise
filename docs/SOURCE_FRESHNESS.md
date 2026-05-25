# Source Freshness

RAG Finland tracks source freshness at the document level so admins can spot stale evidence before users rely on answers.

Each uploaded or connector-imported document gets a source record with:

- `freshness_status`: `fresh`, `aging`, `stale`, `failed`, or `unknown`
- `sync_status`: `synced`, `syncing`, or `failed`
- `last_synced_at`, `source_updated_at`, and `next_sync_at`
- connector type and source URL when available

Defaults are configured with:

```bash
SOURCE_AGING_AFTER_DAYS=30
SOURCE_STALE_AFTER_DAYS=90
SOURCE_SYNC_INTERVAL_HOURS=24
```

Admins can use the Admin Source freshness SLA panel to filter sources, sync one source, or sync all due sources. The due-sync endpoint is also suitable for a cron runner:

```bash
curl -X POST "$API_URL/v1/admin/sources/sync-due?limit=10" \
  -H "Authorization: Bearer $TOKEN"
```

Freshness metadata is included in citations and evidence-pack exports when a source record exists. Analytics also reports stale-source answer rate.
