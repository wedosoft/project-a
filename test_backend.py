#!/usr/bin/env python3
"""
Simple backend server for testing frontend connections
This is a minimal FastAPI server that can run without external dependencies
"""

import json
import time
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional

app = FastAPI(title="Test Backend Server", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check(
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    x_platform: Optional[str] = Header(None, alias="X-Platform"),
    x_domain: Optional[str] = Header(None, alias="X-Domain"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
):
    """
    Health check endpoint for testing frontend connections
    """
    print(f"Health check received:")
    print(f"  X-Tenant-ID: {x_tenant_id}")
    print(f"  X-Platform: {x_platform}")
    print(f"  X-Domain: {x_domain}")
    print(f"  X-API-Key: {x_api_key[:10] + '...' if x_api_key else None}")
    
    # Validate required headers
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="Missing X-Tenant-ID header")
    
    platform = x_platform or "freshdesk"
    
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "platform": platform,
        "tenant_id": x_tenant_id,
        "domain": x_domain,
        "version": "test-1.0.0",
        "services": {
            "api": "healthy",
            "headers_received": {
                "X-Tenant-ID": x_tenant_id,
                "X-Platform": platform,
                "X-Domain": x_domain,
                "X-API-Key": "present" if x_api_key else "missing"
            }
        }
    }

@app.get("/init/{ticket_id}")
async def init_endpoint(
    ticket_id: str,
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    x_platform: Optional[str] = Header(None, alias="X-Platform"),
    x_domain: Optional[str] = Header(None, alias="X-Domain"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
):
    """
    Mock init endpoint for testing
    """
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="Missing X-Tenant-ID header")
    
    return {
        "success": True,
        "ticket_id": ticket_id,
        "tenant_id": x_tenant_id,
        "platform": x_platform or "freshdesk",
        "summary": f"Mock summary for ticket {ticket_id}",
        "similar_tickets": [
            {"id": "123", "subject": "Similar issue 1", "score": 0.95},
            {"id": "456", "subject": "Similar issue 2", "score": 0.87}
        ],
        "kb_documents": [
            {"id": "kb1", "title": "Knowledge base article 1", "score": 0.92},
            {"id": "kb2", "title": "Knowledge base article 2", "score": 0.85}
        ],
        "execution_time": 0.5,
        "search_quality_score": 0.89
    }

@app.post("/ingest")
async def ingest_endpoint(
    x_tenant_id: Optional[str] = Header(None, alias="X-Tenant-ID"),
    x_platform: Optional[str] = Header(None, alias="X-Platform"),
    x_domain: Optional[str] = Header(None, alias="X-Domain"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
):
    """
    Mock ingest endpoint for testing
    """
    if not x_tenant_id:
        raise HTTPException(status_code=400, detail="Missing X-Tenant-ID header")
    
    return {
        "success": True,
        "message": "Mock data ingestion completed",
        "tickets_processed": 150,
        "articles_processed": 25,
        "vectors_created": 1200,
        "processing_time_seconds": 45.2
    }

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting test backend server on http://localhost:8000")
    print("📋 Available endpoints:")
    print("  GET  /health - Health check")
    print("  GET  /init/{ticket_id} - Init endpoint")
    print("  POST /ingest - Data ingestion")
    uvicorn.run(app, host="0.0.0.0", port=8000)