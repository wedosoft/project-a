"""
Unit tests for Freshdesk API Client

Tests:
- Connection initialization
- Retry logic with exponential backoff
- Ticket fetching with pagination
- Conversation fetching
- KB article fetching
- Ticket updates
- Reply posting
- Error handling
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime
import httpx

from backend.services.freshdesk import FreshdeskClient


@pytest.fixture
def freshdesk_client():
    """Fixture for FreshdeskClient instance"""
    return FreshdeskClient()


@pytest.fixture
def mock_response():
    """Fixture for mock HTTP response"""
    response = MagicMock()
    response.json.return_value = {"id": 1, "subject": "Test ticket"}
    response.status_code = 200
    return response


class TestFreshdeskClientInit:
    """Test client initialization"""

    def test_client_initialization(self, freshdesk_client):
        """Test client is initialized with correct config"""
        assert freshdesk_client.base_url.startswith("https://")
        assert freshdesk_client.api_key is not None
        assert freshdesk_client.timeout == 30.0
        assert freshdesk_client.max_retries == 3


class TestMakeRequest:
    """Test _make_request with retry logic"""

    @pytest.mark.asyncio
    async def test_successful_request(self, freshdesk_client, mock_response):
        """Test successful API request"""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.request = AsyncMock(
                return_value=mock_response
            )

            result = await freshdesk_client._make_request("GET", "tickets")

            assert result == {"id": 1, "subject": "Test ticket"}

    @pytest.mark.asyncio
    async def test_retry_on_rate_limit(self, freshdesk_client):
        """Test retry logic on 429 rate limit"""
        with patch("httpx.AsyncClient") as mock_client:
            # First two attempts fail with 429, third succeeds
            error_response = MagicMock()
            error_response.status_code = 429

            success_response = MagicMock()
            success_response.json.return_value = {"id": 1}
            success_response.raise_for_status = MagicMock()

            mock_request = AsyncMock(side_effect=[
                httpx.HTTPStatusError("Rate limited", request=MagicMock(), response=error_response),
                httpx.HTTPStatusError("Rate limited", request=MagicMock(), response=error_response),
                success_response
            ])

            mock_client.return_value.__aenter__.return_value.request = mock_request

            with patch("asyncio.sleep", new_callable=AsyncMock):
                result = await freshdesk_client._make_request("GET", "tickets")

            assert result == {"id": 1}
            assert mock_request.call_count == 3

    @pytest.mark.asyncio
    async def test_retry_exhaustion(self, freshdesk_client):
        """Test failure after max retries"""
        with patch("httpx.AsyncClient") as mock_client:
            error_response = MagicMock()
            error_response.status_code = 500

            mock_request = AsyncMock(side_effect=httpx.HTTPStatusError(
                "Server error", request=MagicMock(), response=error_response
            ))

            mock_client.return_value.__aenter__.return_value.request = mock_request

            with patch("asyncio.sleep", new_callable=AsyncMock):
                with pytest.raises(httpx.HTTPStatusError):
                    await freshdesk_client._make_request("GET", "tickets")

            assert mock_request.call_count == 3


class TestFetchTickets:
    """Test ticket fetching"""

    @pytest.mark.asyncio
    async def test_fetch_tickets_basic(self, freshdesk_client):
        """Test basic ticket fetch without filters"""
        with patch.object(
            freshdesk_client, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            # Return less than per_page to simulate last page
            mock_request.return_value = [{"id": 1}, {"id": 2}]

            result = await freshdesk_client.fetch_tickets()

            # Should be called once with page 1
            mock_request.assert_called_once_with(
                "GET", "tickets", params={"per_page": 30, "page": 1, "order_type": "desc", "order_by": "updated_at"}
            )
            assert len(result) == 2

    @pytest.mark.asyncio
    async def test_fetch_tickets_with_date_filter(self, freshdesk_client):
        """Test ticket fetch with updated_since filter"""
        test_date = datetime(2024, 1, 1, 0, 0, 0)

        with patch.object(
            freshdesk_client, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = [{"id": 1}]

            result = await freshdesk_client.fetch_tickets(updated_since=test_date)

            call_args = mock_request.call_args
            assert call_args[1]["params"]["updated_since"] == test_date.isoformat()

    @pytest.mark.asyncio
    async def test_fetch_tickets_pagination(self, freshdesk_client):
        """Test ticket fetch with internal pagination"""
        with patch.object(
            freshdesk_client, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            # Simulate multiple pages: first page full (30), second page partial (10)
            mock_request.side_effect = [
                [{"id": i} for i in range(1, 31)],  # Page 1: 30 tickets
                [{"id": i} for i in range(31, 41)]  # Page 2: 10 tickets
            ]

            result = await freshdesk_client.fetch_tickets(per_page=30, max_tickets=50)

            # Should be called twice (2 pages)
            assert mock_request.call_count == 2
            assert len(result) == 40  # 30 + 10


class TestGetTicket:
    """Test single ticket retrieval"""

    @pytest.mark.asyncio
    async def test_get_ticket_by_id(self, freshdesk_client):
        """Test fetching ticket by ID"""
        with patch.object(
            freshdesk_client, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = {"id": 123, "subject": "Test"}

            result = await freshdesk_client.get_ticket("123")

            mock_request.assert_called_once_with("GET", "tickets/123")
            assert result["id"] == 123


class TestFetchConversations:
    """Test conversation fetching with pagination"""

    @pytest.mark.asyncio
    async def test_fetch_conversations_single_page(self, freshdesk_client):
        """Test fetching conversations - single page"""
        with patch.object(
            freshdesk_client, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            # Return less than 30 conversations (single page)
            mock_request.return_value = [
                {"id": 1, "body_text": "First message"},
                {"id": 2, "body_text": "Second message"}
            ]

            result = await freshdesk_client.fetch_ticket_conversations("123")

            # Should only call once
            mock_request.assert_called_once()
            assert len(result) == 2

    @pytest.mark.asyncio
    async def test_fetch_conversations_multiple_pages(self, freshdesk_client):
        """Test fetching conversations - multiple pages (pagination)"""
        with patch.object(
            freshdesk_client, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            # Page 1: 30 conversations (full page)
            # Page 2: 21 conversations (partial page)
            mock_request.side_effect = [
                [{"id": i, "body_text": f"Message {i}"} for i in range(1, 31)],  # 30 items
                [{"id": i, "body_text": f"Message {i}"} for i in range(31, 52)]   # 21 items
            ]

            result = await freshdesk_client.fetch_ticket_conversations("123")

            # Should call twice (2 pages)
            assert mock_request.call_count == 2
            assert len(result) == 51  # 30 + 21

    @pytest.mark.asyncio
    async def test_fetch_conversations_empty(self, freshdesk_client):
        """Test fetching conversations - empty result"""
        with patch.object(
            freshdesk_client, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = []

            result = await freshdesk_client.fetch_ticket_conversations("123")

            mock_request.assert_called_once()
            assert len(result) == 0


class TestFetchKBArticles:
    """Test KB article fetching"""

    @pytest.mark.asyncio
    async def test_fetch_kb_articles(self, freshdesk_client):
        """Test fetching KB articles with category/folder hierarchy"""
        with patch.object(
            freshdesk_client, "fetch_kb_categories", new_callable=AsyncMock
        ) as mock_categories:
            with patch.object(
                freshdesk_client, "fetch_kb_folders", new_callable=AsyncMock
            ) as mock_folders:
                with patch.object(
                    freshdesk_client, "_make_request", new_callable=AsyncMock
                ) as mock_request:
                    # Mock category and folder structure
                    mock_categories.return_value = [{"id": 1, "name": "Category 1"}]
                    mock_folders.return_value = [{"id": 10, "name": "Folder 1"}]
                    # Return article from folder
                    mock_request.return_value = [{"id": 100, "title": "Article 1"}]

                    result = await freshdesk_client.fetch_kb_articles(max_articles=10)

                    # Should fetch categories, folders, and articles
                    mock_categories.assert_called_once()
                    mock_folders.assert_called_once()
                    assert len(result) == 1
                    assert result[0]["id"] == 100


class TestUpdateTicketFields:
    """Test ticket field updates"""

    @pytest.mark.asyncio
    async def test_update_ticket_fields(self, freshdesk_client):
        """Test updating ticket fields"""
        updates = {"status": 2, "priority": 3}

        with patch.object(
            freshdesk_client, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = {"id": 123, "status": 2}

            result = await freshdesk_client.update_ticket_fields("123", updates)

            mock_request.assert_called_once_with(
                "PUT", "tickets/123", json=updates
            )
            assert result["status"] == 2


class TestPostReply:
    """Test reply posting"""

    @pytest.mark.asyncio
    async def test_post_public_reply(self, freshdesk_client):
        """Test posting public reply"""
        body = "This is a public response"

        with patch.object(
            freshdesk_client, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = {"id": 456, "body": body}

            result = await freshdesk_client.post_reply("123", body, private=False)

            call_args = mock_request.call_args
            assert call_args[0] == ("POST", "tickets/123/reply")
            assert call_args[1]["json"]["body"] == body
            assert call_args[1]["json"]["private"] is False

    @pytest.mark.asyncio
    async def test_post_private_note(self, freshdesk_client):
        """Test posting private note"""
        body = "Internal note"

        with patch.object(
            freshdesk_client, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = {"id": 789}

            result = await freshdesk_client.add_note("123", body)

            call_args = mock_request.call_args
            assert call_args[0] == ("POST", "tickets/123/notes")
            assert call_args[1]["json"]["private"] is True
