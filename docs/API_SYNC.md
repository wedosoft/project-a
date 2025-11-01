# Sync API Documentation

## Overview

The Sync API provides endpoints for synchronizing Freshdesk data (tickets and KB articles) to the vector database for semantic search and AI-powered assistance.

## Architecture

```
Freshdesk API → Backend Sync Service → Embedding Generation → Qdrant + Supabase
```

**Components:**
- `FreshdeskClient`: Fetches tickets and KB articles from Freshdesk API
- `LLMService`: Generates embeddings using BGE-M3 model
- `QdrantService`: Stores vectors in Qdrant collections
- `SupabaseService`: Logs sync operations for tracking

## Endpoints

### 1. POST /api/sync/tickets

Synchronize tickets from Freshdesk to vector database.

**Query Parameters:**
- `since` (optional): ISO timestamp to filter tickets updated after this time
- `limit` (default: 100, max: 500): Maximum number of tickets to sync

**Request Example:**
```bash
curl -X POST "http://localhost:8000/api/sync/tickets?since=2024-01-01T00:00:00Z&limit=100"
```

**Response:**
```json
{
  "success": true,
  "items_synced": 0,
  "last_sync_time": "2024-11-01T12:00:00",
  "errors": []
}
```

**Process:**
1. Fetches tickets from Freshdesk API with pagination
2. For each ticket:
   - Extracts subject and description
   - Generates embedding using LLMService
   - Stores vector in `support_tickets` collection (Qdrant)
   - Logs sync operation to Supabase
3. Runs in background task for non-blocking operation
4. Returns immediately with initial status

**Collection Schema (Qdrant):**
- Collection: `support_tickets`
- Vectors:
  - `symptom_vec`: Embedding of symptom/problem description
  - `cause_vec`: Embedding of root cause
  - `resolution_vec`: Embedding of resolution/solution
- Payload:
  - `ticket_id`, `subject`, `description`, `content`
  - `status`, `priority`, `type`
  - `created_at`, `updated_at`, `tags`

### 2. POST /api/sync/kb

Synchronize KB articles from Freshdesk to vector database.

**Query Parameters:**
- `since` (optional): ISO timestamp to filter articles updated after this time
- `limit` (default: 100, max: 500): Maximum number of articles to sync

**Request Example:**
```bash
curl -X POST "http://localhost:8000/api/sync/kb?since=2024-01-01T00:00:00Z&limit=50"
```

**Response:**
```json
{
  "success": true,
  "items_synced": 0,
  "last_sync_time": "2024-11-01T12:00:00",
  "errors": []
}
```

**Process:**
1. Fetches KB articles from Freshdesk API with pagination
2. For each article:
   - Extracts title and description
   - Generates embedding using LLMService
   - Stores vector in `kb_procedures` collection (Qdrant)
   - Logs sync operation to Supabase
3. Runs in background task for non-blocking operation

**Collection Schema (Qdrant):**
- Collection: `kb_procedures`
- Vectors:
  - `intent_vec`: Embedding of user intent/question
  - `procedure_vec`: Embedding of step-by-step procedure
- Payload:
  - `article_id`, `title`, `description`, `content`
  - `folder_id`, `category_id`, `status`
  - `created_at`, `updated_at`, `tags`

### 3. GET /api/sync/status

Get current synchronization status and statistics.

**Request Example:**
```bash
curl -X GET "http://localhost:8000/api/sync/status"
```

**Response:**
```json
{
  "last_ticket_sync": "2024-11-01T10:30:00",
  "last_kb_sync": "2024-11-01T09:15:00",
  "total_tickets": 1247,
  "total_kb_articles": 89,
  "sync_in_progress": false
}
```

**Data Sources:**
- `last_ticket_sync`, `last_kb_sync`: From Supabase `sync_logs` table
- `total_tickets`, `total_kb_articles`: From Qdrant collection info
- `sync_in_progress`: From in-memory sync state

## Error Handling

### Rate Limiting (429)

Freshdesk API rate limits are handled with exponential backoff:
- Retry with 2^attempt seconds wait time
- Maximum 3 retries
- Logged as warnings

### Partial Sync Failures

If some items fail during sync:
- Continues processing remaining items
- Returns partial success with error list
- Errors logged with item IDs

**Example:**
```json
{
  "success": true,
  "items_synced": 95,
  "last_sync_time": "2024-11-01T12:00:00",
  "errors": [
    "Failed to process ticket 12345: Empty content",
    "Failed to process ticket 67890: Connection timeout"
  ]
}
```

### Service Unavailable (503)

Returned when:
- Qdrant connection fails
- Supabase connection fails
- Critical service errors

### Conflict (409)

Returned when sync is already in progress:
```json
{
  "detail": "Ticket sync already in progress"
}
```

## Background Processing

Sync operations run in FastAPI BackgroundTasks for non-blocking execution:

**Benefits:**
- Immediate API response
- Long-running sync operations don't block requests
- Progress tracked via `/api/sync/status`

**Implementation:**
```python
background_tasks.add_task(sync_tickets_task, since_dt, limit)
```

## Data Flow

### Ticket Sync Flow

```
1. Freshdesk API
   ↓ fetch_tickets(since, limit, page)
2. Extract Content
   ↓ subject + description → content
3. Generate Embedding
   ↓ LLMService.generate_embedding(content)
4. Store Vector
   ↓ QdrantService.store_vector(collection, id, vectors, payload)
5. Log Sync
   ↓ SupabaseService.log_sync(item_id, collection)
```

### KB Article Sync Flow

```
1. Freshdesk API
   ↓ fetch_kb_articles(since, limit, page)
2. Extract Content
   ↓ title + description → content
3. Generate Embedding
   ↓ LLMService.generate_embedding(content)
4. Store Vector
   ↓ QdrantService.store_vector(kb_procedures, id, vectors, payload)
5. Log Sync
   ↓ SupabaseService.log_sync(item_id, collection)
```

## Database Schema

### Supabase: sync_logs Table

```sql
CREATE TABLE sync_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  collection TEXT NOT NULL,
  item_id TEXT NOT NULL,
  item_type TEXT NOT NULL,  -- 'ticket' | 'kb_article'
  synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  INDEX idx_sync_logs_collection ON sync_logs(collection),
  INDEX idx_sync_logs_synced_at ON sync_logs(synced_at DESC)
);
```

## Usage Examples

### Initial Full Sync

```bash
# Sync all tickets
curl -X POST "http://localhost:8000/api/sync/tickets?limit=500"

# Sync all KB articles
curl -X POST "http://localhost:8000/api/sync/kb?limit=500"
```

### Incremental Sync (Last 24 Hours)

```bash
YESTERDAY=$(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%SZ)

curl -X POST "http://localhost:8000/api/sync/tickets?since=$YESTERDAY&limit=100"
curl -X POST "http://localhost:8000/api/sync/kb?since=$YESTERDAY&limit=100"
```

### Monitor Sync Status

```bash
# Check status every 10 seconds
while true; do
  curl -s "http://localhost:8000/api/sync/status" | jq
  sleep 10
done
```

### Scheduled Sync (Cron)

```bash
# Add to crontab: sync every hour
0 * * * * curl -X POST "http://localhost:8000/api/sync/tickets?since=$(date -u -d '1 hour ago' +\%Y-\%m-\%dT\%H:\%M:\%SZ)&limit=100"
0 * * * * curl -X POST "http://localhost:8000/api/sync/kb?since=$(date -u -d '1 hour ago' +\%Y-\%m-\%dT\%H:\%M:\%SZ)&limit=100"
```

## Performance Considerations

### Pagination

- Freshdesk API: Max 100 items per page
- Sync automatically handles pagination
- Processes all pages until limit reached or no more data

### Batch Processing

- Items processed sequentially within each page
- Future enhancement: Batch embedding generation

### Rate Limits

- Freshdesk API: ~700 requests/minute (varies by plan)
- Automatic retry with exponential backoff on 429
- Consider spacing sync requests

### Resource Usage

**Embedding Generation:**
- BGE-M3 model: ~1GB memory
- ~100ms per embedding
- CPU-bound operation

**Vector Storage:**
- Qdrant: ~1KB per point
- 1000 tickets ≈ 1MB storage

## Troubleshooting

### Empty Content Warnings

```
Empty content for ticket {id}, skipping
```

**Cause:** Ticket has no subject or description
**Action:** Expected behavior, item skipped

### Connection Errors

```
Failed to fetch tickets (page {n}): Connection timeout
```

**Cause:** Network issues or Freshdesk API downtime
**Action:** Retry sync operation later

### Sync Already in Progress

```
409 Conflict: Ticket sync already in progress
```

**Cause:** Previous sync still running
**Action:** Wait or check `/api/sync/status`

### Service Unavailable

```
503 Service Unavailable: Failed to retrieve sync status
```

**Cause:** Qdrant or Supabase connection failed
**Action:** Check service health, verify credentials

## Security Considerations

### API Authentication

- **Current:** No authentication (MVP)
- **Production:** Implement API key or OAuth
- **Recommendation:** Use Freshdesk webhook authentication

### Environment Variables

Required in `.env`:
```env
FRESHDESK_DOMAIN=your-domain
FRESHDESK_API_KEY=your-api-key
QDRANT_HOST=localhost
QDRANT_PORT=6333
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
```

### Rate Limiting

- **Current:** No rate limiting
- **Production:** Implement request throttling
- **Recommendation:** Max 10 sync requests/minute

## Future Enhancements

1. **Webhook Integration**: Real-time sync on Freshdesk updates
2. **Batch Embedding**: Process multiple items in parallel
3. **Incremental Updates**: Update only changed fields
4. **Sync Scheduling**: Built-in cron-like scheduler
5. **Progress Tracking**: WebSocket for real-time progress
6. **Retry Queue**: Automatic retry for failed items
7. **Deduplication**: Skip already-synced items
8. **Delta Sync**: Sync only changed content
