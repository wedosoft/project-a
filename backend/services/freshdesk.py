"""
Freshdesk API Client

Provides comprehensive Freshdesk API integration for:
- Ticket management (fetch, update, conversations)
- KB article management
- Reply posting
- Batch operations with retry logic
"""
import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime
from backend.config import get_settings
from backend.utils.logger import get_logger
import asyncio

settings = get_settings()
logger = get_logger(__name__)


class FreshdeskClient:
    """
    Freshdesk API integration with retry logic and error handling
    """

    def __init__(self):
        self.base_url = f"https://{settings.freshdesk_domain}/api/v2"
        self.api_key = settings.freshdesk_api_key
        self.headers = {
            "Content-Type": "application/json"
        }
        self.timeout = 30.0
        self.max_retries = 3

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Make HTTP request with retry logic

        Args:
            method: HTTP method (GET, POST, PUT, etc.)
            endpoint: API endpoint
            **kwargs: Additional arguments for httpx

        Returns:
            Response JSON

        Raises:
            httpx.HTTPStatusError: On HTTP errors after retries
        """
        url = f"{self.base_url}/{endpoint}"

        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.request(
                        method=method,
                        url=url,
                        auth=(self.api_key, "X"),
                        headers=self.headers,
                        **kwargs
                    )
                    response.raise_for_status()
                    return response.json()

            except httpx.HTTPStatusError as e:
                if e.response.status_code in [429, 500, 502, 503, 504]:
                    # Retry on rate limit or server errors
                    if attempt < self.max_retries - 1:
                        wait_time = 2 ** attempt  # Exponential backoff
                        logger.warning(
                            f"Request failed (attempt {attempt + 1}/{self.max_retries}), "
                            f"retrying in {wait_time}s: {e}"
                        )
                        await asyncio.sleep(wait_time)
                        continue
                raise
            except Exception as e:
                logger.error(f"Request failed: {e}")
                raise

    async def fetch_tickets(
        self,
        updated_since: Optional[datetime] = None,
        per_page: int = 30,
        page: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Fetch tickets with optional filtering

        Args:
            updated_since: Filter tickets updated after this datetime
            per_page: Number of tickets per page (max 100)
            page: Page number

        Returns:
            List of ticket dictionaries
        """
        params = {
            "per_page": min(per_page, 100),
            "page": page
        }

        if updated_since:
            params["updated_since"] = updated_since.isoformat()

        logger.info(f"Fetching tickets (page={page}, per_page={per_page})")
        return await self._make_request("GET", "tickets", params=params)

    async def get_ticket(self, ticket_id: str) -> Dict[str, Any]:
        """
        Get ticket details by ID

        Args:
            ticket_id: Freshdesk ticket ID

        Returns:
            Ticket dictionary with full details
        """
        logger.info(f"Fetching ticket {ticket_id}")
        return await self._make_request("GET", f"tickets/{ticket_id}")

    async def fetch_ticket_conversations(
        self,
        ticket_id: str
    ) -> List[Dict[str, Any]]:
        """
        Fetch all conversations for a ticket with pagination handling

        Args:
            ticket_id: Freshdesk ticket ID

        Returns:
            List of all conversation dictionaries
        """
        all_conversations = []
        page = 1
        per_page = 30  # Freshdesk default page size

        while True:
            logger.info(f"Fetching conversations for ticket {ticket_id} (page {page})")
            conversations = await self._make_request(
                "GET",
                f"tickets/{ticket_id}/conversations",
                params={"per_page": per_page, "page": page}
            )

            if not conversations:
                break

            all_conversations.extend(conversations)

            # If we got less than per_page, we've reached the end
            if len(conversations) < per_page:
                break

            page += 1

        logger.info(f"Fetched total {len(all_conversations)} conversations for ticket {ticket_id}")
        return all_conversations

    async def fetch_kb_articles(
        self,
        updated_since: Optional[datetime] = None,
        per_page: int = 30,
        page: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Fetch KB articles with optional filtering

        Args:
            updated_since: Filter articles updated after this datetime
            per_page: Number of articles per page (max 100)
            page: Page number

        Returns:
            List of KB article dictionaries
        """
        params = {
            "per_page": min(per_page, 100),
            "page": page
        }

        if updated_since:
            params["updated_since"] = updated_since.isoformat()

        logger.info(f"Fetching KB articles (page={page}, per_page={per_page})")
        return await self._make_request(
            "GET",
            "solutions/articles",
            params=params
        )

    async def update_ticket_fields(
        self,
        ticket_id: str,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update ticket fields

        Args:
            ticket_id: Freshdesk ticket ID
            updates: Dictionary of field updates (e.g., {"status": 2, "priority": 3})

        Returns:
            Updated ticket dictionary
        """
        logger.info(f"Updating ticket {ticket_id} with {len(updates)} fields")
        return await self._make_request(
            "PUT",
            f"tickets/{ticket_id}",
            json=updates
        )

    async def post_reply(
        self,
        ticket_id: str,
        body: str,
        private: bool = False
    ) -> Dict[str, Any]:
        """
        Post a reply to a ticket

        Args:
            ticket_id: Freshdesk ticket ID
            body: Reply body (HTML supported)
            private: Whether the reply is private (internal note)

        Returns:
            Reply conversation dictionary
        """
        logger.info(
            f"Posting {'private' if private else 'public'} reply to ticket {ticket_id}"
        )

        payload = {
            "body": body,
            "private": private
        }

        return await self._make_request(
            "POST",
            f"tickets/{ticket_id}/reply",
            json=payload
        )

    async def add_note(
        self,
        ticket_id: str,
        note_body: str,
        private: bool = True
    ) -> Dict[str, Any]:
        """
        Add internal note to ticket

        Args:
            ticket_id: Freshdesk ticket ID
            note_body: Note content
            private: Always True for notes

        Returns:
            Note conversation dictionary
        """
        logger.info(f"Adding note to ticket {ticket_id}")
        return await self._make_request(
            "POST",
            f"tickets/{ticket_id}/notes",
            json={"body": note_body, "private": private}
        )
