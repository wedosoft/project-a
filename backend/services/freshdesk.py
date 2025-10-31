"""
Freshdesk API Client
"""
import httpx
from typing import Dict, Any, Optional
from backend.config import get_settings

settings = get_settings()


class FreshdeskClient:
    """
    Freshdesk API integration
    """

    def __init__(self):
        self.base_url = f"https://{settings.freshdesk_domain}/api/v2"
        self.api_key = settings.freshdesk_api_key
        self.headers = {
            "Content-Type": "application/json"
        }

    async def get_ticket(self, ticket_id: str) -> Dict[str, Any]:
        """Get ticket details"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/tickets/{ticket_id}",
                auth=(self.api_key, "X"),
                headers=self.headers
            )
            response.raise_for_status()
            return response.json()

    async def update_ticket(
        self,
        ticket_id: str,
        field_updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update ticket fields"""
        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{self.base_url}/tickets/{ticket_id}",
                auth=(self.api_key, "X"),
                headers=self.headers,
                json=field_updates
            )
            response.raise_for_status()
            return response.json()

    async def add_note(
        self,
        ticket_id: str,
        note_body: str,
        private: bool = True
    ) -> Dict[str, Any]:
        """Add note to ticket"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/tickets/{ticket_id}/notes",
                auth=(self.api_key, "X"),
                headers=self.headers,
                json={"body": note_body, "private": private}
            )
            response.raise_for_status()
            return response.json()
