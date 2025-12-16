# Research: Freshdesk Copilot UI & Admin

## Decisions

### 1. Freshdesk App Architecture
- **Decision**: Use a **Serverless App** approach where the FDK app (frontend) communicates with our FastAPI backend.
- **Rationale**: Allows complex logic (LangGraph, Vector Search) to run on our infrastructure while keeping the FDK app lightweight.
- **Alternatives**: Server-side app (Crayons UI only), but limited by FDK backend capabilities.

### 2. UI Framework
- **Decision**: **React** with **Freshdesk Crayons** (UI Library).
- **Rationale**: Crayons provides native Freshdesk look & feel. React allows managing complex state (chat, analysis results).
- **Alternatives**: Vanilla JS (hard to maintain), Vue (less ecosystem support in FDK context).

### 3. Admin Interface
- **Decision**: **Full Page App (`admin.html`)** + `iparams.json`.
- **Rationale**:
    - `iparams.json`: Standard way to collect API Key and Domain during installation. No need for custom HTML.
    - **Full Page App (`admin.html`)**: Centralizes all management tasks.
        - **Data Handling**: Trigger sync for Tickets/Articles.
        - **Field Configuration**: Fetch all ticket fields from Freshdesk, display them, and allow the admin to select which ones the Agent should receive suggestions for.
- **Alternatives**: `iparams.html` (unnecessary complexity for simple auth inputs).

### 4. Data Ingestion Strategy
- **Decision**: **Pull-based** sync via Admin Panel + **Webhook** for real-time updates.
- **Rationale**: Initial load via Admin Panel (using Freshdesk API). Real-time updates via Freshdesk Automation Rules (Webhooks) to our backend.

### 5. Additional Admin Features
- **Field Configuration Workflow**:
    1. Admin opens `admin.html`.
    2. App fetches **all ticket fields** (via Freshdesk API).
    3. Admin selects a subset (e.g., "Category", "Priority").
    4. App saves this list to `AdminConfig`.
    5. Agent UI only suggests changes for these selected fields.
- **Prompt Tuning**: Simple controls for response tone (Formal/Casual).


## Unknowns Resolved
- **FDK Sidebar Width**: ~300px. Design must be responsive/adaptive to narrow width.
- **Data Collection**: Use Freshdesk API for historical data, Webhooks for new data.
