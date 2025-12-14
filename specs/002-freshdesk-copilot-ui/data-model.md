# Data Model

## Entities

### TicketAnalysis
Stores the result of AI analysis for a ticket.
- `ticket_id`: string (PK)
- `root_cause`: string
- `solution`: string
- `intent`: string (Enum: Inquiry, Complaint, Request, Technical)
- `sentiment`: string (Enum: Positive, Neutral, Negative)
- `created_at`: datetime

### FieldSuggestion
Proposed updates for ticket fields.
- `id`: uuid (PK)
- `ticket_id`: string (FK)
- `field_name`: string
- `current_value`: string
- `suggested_value`: string
- `confidence`: float
- `reason`: string

### SearchResult
Unified structure for search results.
- `id`: string
- `source`: string (Enum: ticket, article, manual)
- `title`: string
- `snippet`: string
- `url`: string
- `score`: float
- `metadata`: jsonb

### AdminConfig
Configuration for data ingestion and app behavior.
- `tenant_id`: string (PK)
- `freshdesk_domain`: string
- `api_key_encrypted`: string
- `sync_status`: string (Enum: idle, syncing, error)
- `last_sync_at`: datetime
- `selected_fields`: list[string] (List of field names/IDs selected by Admin for AI suggestions)
- `response_tone`: string (Enum: formal, casual)
