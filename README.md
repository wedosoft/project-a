# AI Contact Center OS - Frontend (Freshdesk App)

This repository contains the Frontend application for the AI Contact Center OS, built as a Freshdesk Custom App (FDK).

## Backend

The backend for this project has been migrated to the `agent-platform` repository.
Please refer to that repository for backend setup, API documentation, and agent logic.

## Frontend Setup (Freshdesk FDK)

### Prerequisites
- Node.js 18.x
- Freshdesk CLI (FDK) (`npm install https://dl.freshdev.io/cli/fdk.tgz -g`)

### Installation

1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

### Running Locally

1. Start the FDK local server:
   ```bash
   fdk run
   ```

2. The app will be available at `http://localhost:10001`.
3. To test as a custom app, append `?dev=true` to your Freshdesk ticket URL (e.g., `https://yourdomain.freshdesk.com/a/tickets/1?dev=true`).

### Configuration

- **Backend URL**: Configured in `frontend/app/scripts/backend-config.js`.
  - Development: `ameer-timberless-paragogically.ngrok-free.dev` (or your ngrok URL)
  - Production: `api.wedosoft.net`

## Features

- **Ticket Analysis**: Real-time AI analysis of tickets with field suggestions.
- **Chat Copilot**: RAG-based chat interface for querying knowledge base and ticket history.
- **Streaming**: SSE (Server-Sent Events) support for real-time responses.
