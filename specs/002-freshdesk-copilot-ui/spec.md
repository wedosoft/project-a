# Freshdesk Custom App (AI Copilot) UX/UI Plan

## Goal
Design the UX/UI for the Freshdesk custom app "AI Copilot" (right sidebar) considering agent efficiency.

## Features
1. **Ticket Field Suggestions**: Propose updates to ticket fields.
2. **Ticket Analysis**: Analyze root cause, solution, customer intent, and sentiment.
3. **Chat Search**: Search across Tickets, Articles, and Product Manuals.

## Constraints & Context
- Currently, only **Product Manual** data exists.
- **Tickets** and **Articles** are to be collected.
- **Admin Interface** is required to manage/collect this data.

## Requirements
- **Sidebar App (Agent View)**:
    - Efficient layout for analysis and suggestions.
    - Chat interface for search.
    - **Field Suggestions**: Only display suggestions for fields selected by the Admin.
- **Admin App (Full Page View)**:
    - **Data Management**: Trigger sync for Tickets/Articles.
    - **Field Configuration**:
        - Fetch all available ticket fields from Freshdesk.
        - UI to select "Target Fields" for AI suggestions.
        - Save selection to backend.
    - **(Proposed) Analytics**: Dashboard showing AI adoption rate.

## Proposed Additional Features
- **Prompt Customization**: Allow admins to set the tone (Formal/Casual) of the AI response.
- **Feedback Loop**: View rejected suggestions to understand AI performance gaps.
