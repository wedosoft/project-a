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
from datetime import datetime, timezone as dt_timezone
from dateutil import parser as date_parser
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
        max_tickets: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch tickets with optional filtering and pagination

        Args:
            updated_since: Filter tickets updated after this datetime
            per_page: Number of tickets per page (max 100)
            max_tickets: Maximum number of tickets to fetch (None = all pages)

        Returns:
            List of ticket dictionaries
        """
        all_tickets = []
        page = 1
        per_page = min(per_page, 100)

        while True:
            params = {
                "per_page": per_page,
                "page": page,
                "order_type": "desc",
                "order_by": "updated_at"
            }

            if updated_since:
                params["updated_since"] = updated_since.isoformat()

            logger.info(f"Fetching tickets (page={page}, per_page={per_page})")
            tickets = await self._make_request("GET", "tickets", params=params)

            if not tickets:
                break

            all_tickets.extend(tickets)
            logger.info(f"Fetched page {page}: {len(tickets)} tickets (total: {len(all_tickets)})")

            # Stop if we've reached max_tickets
            if max_tickets and len(all_tickets) >= max_tickets:
                all_tickets = all_tickets[:max_tickets]
                break

            # Stop if last page (less than per_page means last page)
            if len(tickets) < per_page:
                break

            page += 1

        logger.info(f"Successfully fetched total {len(all_tickets)} tickets")
        return all_tickets

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

    async def fetch_kb_categories(self) -> List[Dict[str, Any]]:
        """
        Fetch all KB categories

        Returns:
            List of category dictionaries with category IDs and metadata
        """
        logger.info("Fetching KB categories")
        categories = await self._make_request("GET", "solutions/categories")
        logger.info(f"Found {len(categories)} KB categories")
        return categories

    async def fetch_kb_folders(self, category_id: str) -> List[Dict[str, Any]]:
        """
        Fetch all folders in a KB category

        Args:
            category_id: Category ID

        Returns:
            List of folder dictionaries with folder IDs and metadata
        """
        logger.info(f"Fetching folders for category {category_id}")
        folders = await self._make_request("GET", f"solutions/categories/{category_id}/folders")
        logger.info(f"Found {len(folders)} folders in category {category_id}")
        return folders

    async def fetch_kb_articles(
        self,
        updated_since: Optional[datetime] = None,
        per_page: int = 30,
        max_articles: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch KB articles from all categories/folders with pagination

        Freshdesk KB hierarchy: Categories → Folders → Articles

        Args:
            updated_since: Filter articles updated after this datetime
            per_page: Number of articles per page (max 100)
            max_articles: Maximum total number of articles to fetch

        Returns:
            List of KB article dictionaries
        """
        all_articles = []
        per_page = min(per_page, 100)

        # Step 1: Fetch all categories
        try:
            categories = await self.fetch_kb_categories()
        except Exception as e:
            logger.error(f"Failed to fetch KB categories: {e}")
            return []

        # Step 2: Iterate through categories and their folders
        for category in categories:
            category_id = category.get('id')
            if not category_id:
                continue

            logger.info(f"Processing category {category_id} ({category.get('name', 'Unknown')})")

            # Step 3: Fetch folders in this category
            try:
                folders = await self.fetch_kb_folders(str(category_id))
            except Exception as e:
                logger.warning(f"Failed to fetch folders for category {category_id}: {e}")
                continue

            # Step 4: Iterate through folders and fetch articles with pagination
            for folder in folders:
                folder_id = folder.get('id')
                if not folder_id:
                    continue

                logger.info(f"Fetching articles from folder {folder_id} ({folder.get('name', 'Unknown')})")
                page = 1

                while True:
                    params = {
                        "per_page": per_page,
                        "page": page
                    }

                    # Note: KB articles endpoint does not support updated_since parameter
                    # We fetch all articles and filter client-side if needed

                    try:
                        articles = await self._make_request(
                            "GET",
                            f"solutions/folders/{folder_id}/articles",
                            params=params
                        )

                        if not articles:
                            break

                        # Client-side filtering by updated_since if provided
                        if updated_since:
                            filtered_articles = []
                            for article in articles:
                                updated_at_str = article.get('updated_at')
                                if updated_at_str:
                                    try:
                                        # Parse ISO format datetime
                                        article_updated_at = date_parser.isoparse(updated_at_str)

                                        # Make both timezone-aware for comparison
                                        if article_updated_at.tzinfo is None:
                                            article_updated_at = article_updated_at.replace(tzinfo=dt_timezone.utc)
                                        if updated_since.tzinfo is None:
                                            updated_since_aware = updated_since.replace(tzinfo=dt_timezone.utc)
                                        else:
                                            updated_since_aware = updated_since

                                        # Only include articles updated after the threshold
                                        if article_updated_at >= updated_since_aware:
                                            filtered_articles.append(article)
                                    except Exception as e:
                                        logger.warning(f"Failed to parse updated_at for article {article.get('id')}: {e}")
                                        # Include article if we can't parse date
                                        filtered_articles.append(article)
                                else:
                                    # Include articles without updated_at
                                    filtered_articles.append(article)

                            articles = filtered_articles
                            logger.info(f"Filtered to {len(articles)} articles after updated_since check")

                        if not articles:
                            # All articles filtered out, move to next page
                            page += 1
                            continue

                        all_articles.extend(articles)
                        logger.info(f"Fetched page {page} from folder {folder_id}: {len(articles)} articles (total: {len(all_articles)})")

                        # Stop if we've reached max_articles
                        if max_articles and len(all_articles) >= max_articles:
                            all_articles = all_articles[:max_articles]
                            logger.info(f"Reached max_articles limit: {max_articles}")
                            return all_articles

                        # Stop if last page (less than per_page means last page)
                        if len(articles) < per_page:
                            break

                        page += 1

                    except Exception as e:
                        logger.warning(f"Failed to fetch articles from folder {folder_id}: {e}")
                        break

        logger.info(f"Successfully fetched total {len(all_articles)} articles from all categories/folders")
        return all_articles

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
