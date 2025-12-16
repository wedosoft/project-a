# Tasks: Freshdesk Copilot UI

**Feature**: Freshdesk Copilot UI & Admin
**Status**: Completed

## Phase 1: Setup & Configuration
- [x] T001 Create `AdminConfig` model in `agent-platform/app/models/admin.py` with `selected_fields` and `response_tone`
- [x] T002 Implement `/api/admin/config` GET/PUT endpoints in `agent-platform/app/api/routes/admin.py`

## Phase 2: Admin Interface (User Story 4)
**Goal**: Enable admins to configure the AI Copilot.
- [x] T003 [US4] Create `admin.html` in `project-a/frontend/app/`
- [x] T004 [US4] Add `admin.js` in `project-a/frontend/app/scripts/` for Admin UI logic
- [x] T005 [US4] Implement "Fetch Ticket Fields" logic in `admin.js` using FDK Request API
- [x] T006 [US4] Implement "Field Selection" UI in `admin.html` (checkbox list of fields)
- [x] T007 [US4] Implement "Save Configuration" logic in `admin.js` (call `/api/admin/config`)
- [x] T008 [US4] Implement "Sync Data" button in `admin.html` (call `/api/admin/sync`)
- [x] T009 [US4] Update `project-a/frontend/manifest.json` to include `admin.html` location

## Phase 3: Analysis & Suggestions (User Story 1 & 2)
**Goal**: Display AI analysis and field suggestions in the sidebar.
- [x] T010 [US1] Update `agent-platform/app/agents/analyzer.py` to accept and use `response_tone`
- [x] T011 [US1] Update `agent-platform/app/api/routes/assist.py` to filter suggestions based on `selected_fields`
- [x] T012 [US2] Create `sidebar.js` in `project-a/frontend/app/scripts/` (if not exists) or update `app.js`
- [x] T013 [US2] Implement "Analysis View" in `project-a/frontend/app/index.html` (Root Cause, Solution, Intent, Sentiment)
- [x] T014 [US1] Implement "Field Suggestions View" in `project-a/frontend/app/index.html`
- [x] T015 [US1] Implement "Apply Suggestion" logic in `sidebar.js` (using FDK Interface API to set field values)

## Phase 4: Chat Search (User Story 3)
**Goal**: Unified search across tickets, articles, and manuals.
- [x] T016 [US3] Verify `/api/search` endpoint in `agent-platform/app/api/routes/chat.py` supports unified search
- [x] T017 [US3] Add "Chat Tab" to `project-a/frontend/app/index.html`
- [x] T018 [US3] Implement Chat UI (Input, Message List) in `project-a/frontend/app/index.html`
- [x] T019 [US3] Implement Search logic in `sidebar.js` (call `/api/search`)

## Phase 5: Polish
- [x] T020 Apply Freshdesk Crayons styles to `admin.html`
- [x] T021 Apply Freshdesk Crayons styles to `index.html` (Sidebar)

## Dependencies
- US1 depends on US4 (Config)
- US2 is independent
- US3 is independent

## Implementation Strategy
- Start with Backend Config (Phase 1)
- Build Admin UI to populate Config (Phase 2)
- Build Sidebar UI to consume Config and display Analysis (Phase 3)
