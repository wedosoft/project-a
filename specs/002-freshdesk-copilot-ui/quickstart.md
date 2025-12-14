# Quickstart

## Prerequisites
- Python 3.9+
- Node.js 18+
- Freshdesk Account (Trial or Paid)
- FDK CLI (`npm install https://dl.freshdev.io/cli/fdk.tgz -g`)

## Backend Setup
1. Navigate to `backend/`
2. Install dependencies: `pip install -r requirements.txt`
3. Run server: `uvicorn main:app --reload`

## Frontend (FDK App) Setup
1. Navigate to `frontend/`
2. Install dependencies: `npm install`
3. Run app: `fdk run`
4. Go to `http://localhost:10001/custom_configs` to configure settings.
5. Open a ticket in Freshdesk and append `?dev=true` to the URL to see the app.

## Admin Interface
1. Access the app settings page in Freshdesk (or via `http://localhost:10001/custom_configs` locally).
2. Configure API Key and Domain.
3. Click "Sync Data" to ingest Tickets and Articles.
