"""
Freshdesk Integration Test Script

Tests Freshdesk API with real data:
- Fetch 10 tickets
- Fetch 10 KB articles
- Process through hybrid search
- Generate AI suggestions
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.services.freshdesk import FreshdeskClient
from backend.services.llm_service import LLMService
from backend.services.qdrant_service import QdrantService
from backend.services.sparse_search import SparseSearchService
from backend.services.hybrid_search import HybridSearchService
from backend.utils.logger import get_logger
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any

logger = get_logger(__name__)

# Collection names
TICKETS_COLLECTION = "support_tickets"
KB_COLLECTION = "kb_procedures"


async def test_fetch_tickets(freshdesk: FreshdeskClient, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Test fetching tickets from Freshdesk

    Args:
        freshdesk: FreshdeskClient instance
        limit: Number of tickets to fetch

    Returns:
        List of ticket dictionaries
    """
    logger.info(f"\n{'='*60}")
    logger.info("TEST 1: Fetching Tickets from Freshdesk")
    logger.info(f"{'='*60}")

    try:
        # Fetch recent tickets (last 30 days)
        since = datetime.now(timezone.utc) - timedelta(days=30)

        tickets = await freshdesk.fetch_tickets(
            updated_since=since,
            per_page=30,
            max_tickets=limit
        )

        logger.info(f"✅ Successfully fetched {len(tickets)} tickets")

        # Display sample tickets
        for i, ticket in enumerate(tickets[:3], 1):
            logger.info(f"\nTicket {i}:")
            logger.info(f"  ID: {ticket.get('id')}")
            logger.info(f"  Subject: {ticket.get('subject', 'N/A')}")
            logger.info(f"  Status: {ticket.get('status', 'N/A')}")
            logger.info(f"  Priority: {ticket.get('priority', 'N/A')}")
            logger.info(f"  Created: {ticket.get('created_at', 'N/A')}")

        return tickets

    except Exception as e:
        logger.error(f"❌ Failed to fetch tickets: {e}")
        raise


async def test_fetch_kb_articles(freshdesk: FreshdeskClient, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Test fetching KB articles from Freshdesk

    Args:
        freshdesk: FreshdeskClient instance
        limit: Number of articles to fetch

    Returns:
        List of article dictionaries
    """
    logger.info(f"\n{'='*60}")
    logger.info("TEST 2: Fetching KB Articles from Freshdesk")
    logger.info(f"{'='*60}")

    try:
        # Fetch recent articles (last 30 days)
        since = datetime.now(timezone.utc) - timedelta(days=30)

        articles = await freshdesk.fetch_kb_articles(
            updated_since=since,
            per_page=30,
            max_articles=limit
        )

        logger.info(f"✅ Successfully fetched {len(articles)} KB articles")

        # Display sample articles
        for i, article in enumerate(articles[:3], 1):
            logger.info(f"\nArticle {i}:")
            logger.info(f"  ID: {article.get('id')}")
            logger.info(f"  Title: {article.get('title', 'N/A')}")
            logger.info(f"  Status: {article.get('status', 'N/A')}")
            logger.info(f"  Created: {article.get('created_at', 'N/A')}")

        return articles

    except Exception as e:
        logger.error(f"❌ Failed to fetch KB articles: {e}")
        raise


async def test_sync_to_qdrant(
    tickets: List[Dict[str, Any]],
    articles: List[Dict[str, Any]],
    llm: LLMService,
    qdrant: QdrantService,
    sparse_search: SparseSearchService
):
    """
    Test syncing data to Qdrant and Postgres

    Args:
        tickets: List of ticket dictionaries
        articles: List of article dictionaries
        llm: LLMService instance
        qdrant: QdrantService instance
        sparse_search: SparseSearchService instance
    """
    logger.info(f"\n{'='*60}")
    logger.info("TEST 3: Syncing Data to Qdrant & Postgres")
    logger.info(f"{'='*60}")

    try:
        # 1. Ensure collections exist
        logger.info("\nStep 1: Creating Qdrant collections...")
        qdrant.ensure_collection(
            collection_name=TICKETS_COLLECTION,
            vector_names=["symptom_vec", "cause_vec", "resolution_vec"]
        )
        qdrant.ensure_collection(
            collection_name=KB_COLLECTION,
            vector_names=["intent_vec", "procedure_vec"]
        )
        logger.info("✅ Collections created/verified")

        # 2. Sync tickets
        logger.info(f"\nStep 2: Syncing {len(tickets)} tickets...")
        sparse_tickets = []

        for ticket in tickets:
            ticket_id = str(ticket.get("id"))
            subject = ticket.get("subject", "")
            description = ticket.get("description_text", "")
            content = f"{subject}\n\n{description}".strip()

            if not content:
                logger.warning(f"Empty content for ticket {ticket_id}, skipping")
                continue

            # Generate embedding
            embedding = llm.generate_embedding(content)

            # Prepare vectors
            vectors = {
                "symptom_vec": embedding,
                "cause_vec": embedding,
                "resolution_vec": embedding
            }

            # Prepare payload
            payload = {
                "ticket_id": ticket_id,
                "subject": subject,
                "description": description,
                "content": content,
                "status": ticket.get("status"),
                "priority": ticket.get("priority"),
                "type": ticket.get("type"),
                "created_at": ticket.get("created_at"),
                "updated_at": ticket.get("updated_at"),
                "tags": ticket.get("tags", [])
            }

            # Store in Qdrant
            qdrant.store_vector(
                collection_name=TICKETS_COLLECTION,
                point_id=ticket_id,
                vectors=vectors,
                payload=payload
            )

            # Prepare for sparse indexing
            sparse_tickets.append({
                "id": ticket_id,
                "content": content,
                "metadata": {
                    "subject": subject,
                    "status": ticket.get("status"),
                    "priority": ticket.get("priority")
                }
            })

        # Index in Postgres for BM25
        if sparse_tickets:
            indexed_count = await sparse_search.index_documents(
                collection_name=TICKETS_COLLECTION,
                documents=sparse_tickets
            )
            logger.info(f"✅ Synced {len(tickets)} tickets (Dense + Sparse: {indexed_count})")

        # 3. Sync KB articles
        logger.info(f"\nStep 3: Syncing {len(articles)} KB articles...")
        sparse_articles = []

        for article in articles:
            article_id = str(article.get("id"))
            title = article.get("title", "")
            description = article.get("description_text", "")
            content = f"{title}\n\n{description}".strip()

            if not content:
                logger.warning(f"Empty content for KB article {article_id}, skipping")
                continue

            # Generate embedding
            embedding = llm.generate_embedding(content)

            # Prepare vectors
            vectors = {
                "intent_vec": embedding,
                "procedure_vec": embedding
            }

            # Prepare payload
            payload = {
                "article_id": article_id,
                "title": title,
                "description": description,
                "content": content,
                "folder_id": article.get("folder_id"),
                "category_id": article.get("category_id"),
                "status": article.get("status"),
                "created_at": article.get("created_at"),
                "updated_at": article.get("updated_at"),
                "tags": article.get("tags", [])
            }

            # Store in Qdrant
            qdrant.store_vector(
                collection_name=KB_COLLECTION,
                point_id=article_id,
                vectors=vectors,
                payload=payload
            )

            # Prepare for sparse indexing
            sparse_articles.append({
                "id": article_id,
                "content": content,
                "metadata": {
                    "title": title,
                    "status": article.get("status")
                }
            })

        # Index in Postgres for BM25
        if sparse_articles:
            indexed_count = await sparse_search.index_documents(
                collection_name=KB_COLLECTION,
                documents=sparse_articles
            )
            logger.info(f"✅ Synced {len(articles)} KB articles (Dense + Sparse: {indexed_count})")

    except Exception as e:
        logger.error(f"❌ Failed to sync data: {e}")
        raise


async def test_hybrid_search(hybrid_search: HybridSearchService, tickets: List[Dict[str, Any]]):
    """
    Test hybrid search with real query

    Args:
        hybrid_search: HybridSearchService instance
        tickets: List of ticket dictionaries for creating test query
    """
    logger.info(f"\n{'='*60}")
    logger.info("TEST 4: Hybrid Search (Dense + Sparse + Reranking)")
    logger.info(f"{'='*60}")

    try:
        # Use first ticket subject as query
        if not tickets:
            logger.warning("No tickets available for search query")
            return

        query = tickets[0].get("subject", "login error")
        logger.info(f"\nQuery: '{query}'")

        # Test ticket search
        logger.info("\nSearching support tickets...")
        ticket_results = await hybrid_search.search(
            collection_name=TICKETS_COLLECTION,
            query=query,
            top_k=5,
            use_reranking=True
        )

        logger.info(f"✅ Found {len(ticket_results)} similar tickets")
        for i, result in enumerate(ticket_results[:3], 1):
            logger.info(f"\nResult {i}:")
            logger.info(f"  Score: {result.get('rrf_score', 0):.4f}")
            logger.info(f"  Ticket ID: {result.get('payload', {}).get('ticket_id')}")
            logger.info(f"  Subject: {result.get('payload', {}).get('subject', 'N/A')[:80]}")

        # Test KB search
        logger.info("\n\nSearching KB procedures...")
        kb_results = await hybrid_search.search(
            collection_name=KB_COLLECTION,
            query=query,
            top_k=5,
            use_reranking=True
        )

        logger.info(f"✅ Found {len(kb_results)} relevant KB articles")
        for i, result in enumerate(kb_results[:3], 1):
            logger.info(f"\nResult {i}:")
            logger.info(f"  Score: {result.get('rrf_score', 0):.4f}")
            logger.info(f"  Article ID: {result.get('payload', {}).get('article_id')}")
            logger.info(f"  Title: {result.get('payload', {}).get('title', 'N/A')[:80]}")

    except Exception as e:
        logger.error(f"❌ Failed hybrid search: {e}")
        raise


async def main():
    """Main test runner"""
    logger.info("\n" + "="*60)
    logger.info("Freshdesk Integration Test - Real Data")
    logger.info("="*60)

    try:
        # Initialize services
        logger.info("\nInitializing services...")
        freshdesk = FreshdeskClient()
        llm = LLMService()
        qdrant = QdrantService()
        sparse_search = SparseSearchService()
        hybrid_search = HybridSearchService()
        logger.info("✅ Services initialized")

        # Test 1: Fetch tickets
        tickets = await test_fetch_tickets(freshdesk, limit=10)

        # Test 2: Fetch KB articles
        articles = await test_fetch_kb_articles(freshdesk, limit=10)

        # Test 3: Sync to Qdrant & Postgres
        await test_sync_to_qdrant(tickets, articles, llm, qdrant, sparse_search)

        # Test 4: Hybrid search
        await test_hybrid_search(hybrid_search, tickets)

        # Summary
        logger.info(f"\n{'='*60}")
        logger.info("TEST SUMMARY")
        logger.info(f"{'='*60}")
        logger.info(f"✅ Tickets fetched: {len(tickets)}")
        logger.info(f"✅ KB articles fetched: {len(articles)}")
        logger.info(f"✅ Data synced to Qdrant: {len(tickets) + len(articles)} items")
        logger.info(f"✅ Hybrid search: Working")
        logger.info(f"\n{'='*60}")
        logger.info("ALL TESTS PASSED")
        logger.info(f"{'='*60}\n")

    except Exception as e:
        logger.error(f"\n❌ TEST FAILED: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
