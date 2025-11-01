"""
Synchronization API Routes

Provides endpoints for syncing Freshdesk data to vector database:
- Ticket synchronization with embeddings
- KB article synchronization
- Sync status monitoring
"""
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
import asyncio

from backend.services.freshdesk import FreshdeskClient
from backend.services.llm_service import LLMService
from backend.services.qdrant_service import QdrantService
from backend.services.supabase_client import SupabaseService
from backend.utils.logger import get_logger
from backend.config import get_settings

router = APIRouter()
logger = get_logger(__name__)
settings = get_settings()

# Service instances
freshdesk = FreshdeskClient()
llm = LLMService()
qdrant = QdrantService()
supabase = SupabaseService()

# Collection names
TICKETS_COLLECTION = "support_tickets"
KB_COLLECTION = "kb_procedures"


# Pydantic Models
class SyncRequest(BaseModel):
    """Sync request parameters"""
    since: Optional[str] = Field(None, description="ISO timestamp for filtering updated items")
    limit: int = Field(100, ge=1, le=500, description="Maximum items to sync per request")


class SyncResult(BaseModel):
    """Sync operation result"""
    success: bool
    items_synced: int
    last_sync_time: str
    errors: List[str] = []


class SyncStatus(BaseModel):
    """Current sync status"""
    last_ticket_sync: Optional[str] = None
    last_kb_sync: Optional[str] = None
    total_tickets: int = 0
    total_kb_articles: int = 0
    sync_in_progress: bool = False


# Global sync state
sync_state = {
    "ticket_sync_in_progress": False,
    "kb_sync_in_progress": False
}


async def sync_tickets_task(since: Optional[datetime], limit: int) -> SyncResult:
    """
    Background task for ticket synchronization

    Args:
        since: Filter tickets updated after this datetime
        limit: Maximum number of tickets to sync

    Returns:
        SyncResult with sync statistics
    """
    sync_state["ticket_sync_in_progress"] = True
    errors = []
    synced_count = 0
    last_sync = datetime.utcnow().isoformat()

    try:
        # Ensure collection exists
        qdrant.ensure_collection(
            collection_name=TICKETS_COLLECTION,
            vector_names=["symptom_vec", "cause_vec", "resolution_vec"]
        )

        # Fetch tickets from Freshdesk
        page = 1
        total_fetched = 0

        while total_fetched < limit:
            per_page = min(100, limit - total_fetched)

            try:
                tickets = await freshdesk.fetch_tickets(
                    updated_since=since,
                    per_page=per_page,
                    page=page
                )

                if not tickets:
                    break

                logger.info(f"Fetched {len(tickets)} tickets (page {page})")

                # Process each ticket
                for ticket in tickets:
                    try:
                        # Extract text content
                        ticket_id = str(ticket.get("id"))
                        subject = ticket.get("subject", "")
                        description = ticket.get("description_text", "")

                        # Combine for embedding
                        content = f"{subject}\n\n{description}".strip()

                        if not content:
                            logger.warning(f"Empty content for ticket {ticket_id}, skipping")
                            continue

                        # Generate embeddings
                        embedding = llm.generate_embedding(content)

                        # Prepare vectors (use same embedding for all fields for now)
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

                        # Log to Supabase
                        await supabase.client.table("sync_logs").insert({
                            "collection": TICKETS_COLLECTION,
                            "item_id": ticket_id,
                            "synced_at": datetime.utcnow().isoformat(),
                            "item_type": "ticket"
                        }).execute()

                        synced_count += 1

                    except Exception as e:
                        error_msg = f"Failed to process ticket {ticket.get('id')}: {str(e)}"
                        logger.error(error_msg)
                        errors.append(error_msg)

                total_fetched += len(tickets)

                # Check if we've reached the end
                if len(tickets) < per_page:
                    break

                page += 1

            except Exception as e:
                error_msg = f"Failed to fetch tickets (page {page}): {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
                break

        logger.info(f"Ticket sync completed: {synced_count} tickets synced, {len(errors)} errors")

        return SyncResult(
            success=len(errors) == 0 or synced_count > 0,
            items_synced=synced_count,
            last_sync_time=last_sync,
            errors=errors
        )

    except Exception as e:
        error_msg = f"Ticket sync failed: {str(e)}"
        logger.error(error_msg)
        return SyncResult(
            success=False,
            items_synced=synced_count,
            last_sync_time=last_sync,
            errors=[error_msg]
        )

    finally:
        sync_state["ticket_sync_in_progress"] = False


async def sync_kb_task(since: Optional[datetime], limit: int) -> SyncResult:
    """
    Background task for KB article synchronization

    Args:
        since: Filter articles updated after this datetime
        limit: Maximum number of articles to sync

    Returns:
        SyncResult with sync statistics
    """
    sync_state["kb_sync_in_progress"] = True
    errors = []
    synced_count = 0
    last_sync = datetime.utcnow().isoformat()

    try:
        # Ensure collection exists
        qdrant.ensure_collection(
            collection_name=KB_COLLECTION,
            vector_names=["intent_vec", "procedure_vec"]
        )

        # Fetch KB articles from Freshdesk
        page = 1
        total_fetched = 0

        while total_fetched < limit:
            per_page = min(100, limit - total_fetched)

            try:
                articles = await freshdesk.fetch_kb_articles(
                    updated_since=since,
                    per_page=per_page,
                    page=page
                )

                if not articles:
                    break

                logger.info(f"Fetched {len(articles)} KB articles (page {page})")

                # Process each article
                for article in articles:
                    try:
                        # Extract text content
                        article_id = str(article.get("id"))
                        title = article.get("title", "")
                        description = article.get("description_text", "")

                        # Combine for embedding
                        content = f"{title}\n\n{description}".strip()

                        if not content:
                            logger.warning(f"Empty content for KB article {article_id}, skipping")
                            continue

                        # Generate embeddings
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

                        # Log to Supabase
                        await supabase.client.table("sync_logs").insert({
                            "collection": KB_COLLECTION,
                            "item_id": article_id,
                            "synced_at": datetime.utcnow().isoformat(),
                            "item_type": "kb_article"
                        }).execute()

                        synced_count += 1

                    except Exception as e:
                        error_msg = f"Failed to process KB article {article.get('id')}: {str(e)}"
                        logger.error(error_msg)
                        errors.append(error_msg)

                total_fetched += len(articles)

                # Check if we've reached the end
                if len(articles) < per_page:
                    break

                page += 1

            except Exception as e:
                error_msg = f"Failed to fetch KB articles (page {page}): {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
                break

        logger.info(f"KB sync completed: {synced_count} articles synced, {len(errors)} errors")

        return SyncResult(
            success=len(errors) == 0 or synced_count > 0,
            items_synced=synced_count,
            last_sync_time=last_sync,
            errors=errors
        )

    except Exception as e:
        error_msg = f"KB sync failed: {str(e)}"
        logger.error(error_msg)
        return SyncResult(
            success=False,
            items_synced=synced_count,
            last_sync_time=last_sync,
            errors=[error_msg]
        )

    finally:
        sync_state["kb_sync_in_progress"] = False


@router.post("/tickets", response_model=SyncResult)
async def sync_tickets(
    background_tasks: BackgroundTasks,
    since: Optional[str] = Query(None, description="ISO timestamp for filtering"),
    limit: int = Query(100, ge=1, le=500, description="Maximum tickets to sync")
):
    """
    Synchronize tickets from Freshdesk

    - Fetches tickets from Freshdesk API
    - Generates embeddings using LLM service
    - Stores vectors in Qdrant
    - Logs sync activity to Supabase

    Args:
        since: ISO timestamp to filter tickets updated after this time
        limit: Maximum number of tickets to sync (1-500)

    Returns:
        SyncResult with sync statistics
    """
    if sync_state["ticket_sync_in_progress"]:
        raise HTTPException(
            status_code=409,
            detail="Ticket sync already in progress"
        )

    # Parse since parameter
    since_dt = None
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid ISO timestamp format for 'since' parameter"
            )

    # Run sync in background
    background_tasks.add_task(sync_tickets_task, since_dt, limit)

    return SyncResult(
        success=True,
        items_synced=0,
        last_sync_time=datetime.utcnow().isoformat(),
        errors=[]
    )


@router.post("/kb", response_model=SyncResult)
async def sync_kb_articles(
    background_tasks: BackgroundTasks,
    since: Optional[str] = Query(None, description="ISO timestamp for filtering"),
    limit: int = Query(100, ge=1, le=500, description="Maximum articles to sync")
):
    """
    Synchronize KB articles from Freshdesk

    - Fetches KB articles from Freshdesk API
    - Generates embeddings using LLM service
    - Stores vectors in Qdrant kb_procedures collection
    - Logs sync activity to Supabase

    Args:
        since: ISO timestamp to filter articles updated after this time
        limit: Maximum number of articles to sync (1-500)

    Returns:
        SyncResult with sync statistics
    """
    if sync_state["kb_sync_in_progress"]:
        raise HTTPException(
            status_code=409,
            detail="KB sync already in progress"
        )

    # Parse since parameter
    since_dt = None
    if since:
        try:
            since_dt = datetime.fromisoformat(since.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid ISO timestamp format for 'since' parameter"
            )

    # Run sync in background
    background_tasks.add_task(sync_kb_task, since_dt, limit)

    return SyncResult(
        success=True,
        items_synced=0,
        last_sync_time=datetime.utcnow().isoformat(),
        errors=[]
    )


@router.get("/status", response_model=SyncStatus)
async def get_sync_status():
    """
    Get current synchronization status

    Returns:
        - Last sync timestamps for tickets and KB articles
        - Total counts from Qdrant collections
        - Current sync operation status
    """
    try:
        # Get last sync times from Supabase
        ticket_sync_result = await supabase.client.table("sync_logs") \
            .select("synced_at") \
            .eq("collection", TICKETS_COLLECTION) \
            .order("synced_at", desc=True) \
            .limit(1) \
            .execute()

        kb_sync_result = await supabase.client.table("sync_logs") \
            .select("synced_at") \
            .eq("collection", KB_COLLECTION) \
            .order("synced_at", desc=True) \
            .limit(1) \
            .execute()

        last_ticket_sync = None
        if ticket_sync_result.data:
            last_ticket_sync = ticket_sync_result.data[0]["synced_at"]

        last_kb_sync = None
        if kb_sync_result.data:
            last_kb_sync = kb_sync_result.data[0]["synced_at"]

        # Get counts from Qdrant
        total_tickets = 0
        total_kb_articles = 0

        try:
            ticket_info = qdrant.get_collection_info(TICKETS_COLLECTION)
            total_tickets = ticket_info.get("points_count", 0)
        except Exception as e:
            logger.warning(f"Failed to get ticket collection info: {e}")

        try:
            kb_info = qdrant.get_collection_info(KB_COLLECTION)
            total_kb_articles = kb_info.get("points_count", 0)
        except Exception as e:
            logger.warning(f"Failed to get KB collection info: {e}")

        # Check if sync is in progress
        sync_in_progress = (
            sync_state["ticket_sync_in_progress"] or
            sync_state["kb_sync_in_progress"]
        )

        return SyncStatus(
            last_ticket_sync=last_ticket_sync,
            last_kb_sync=last_kb_sync,
            total_tickets=total_tickets,
            total_kb_articles=total_kb_articles,
            sync_in_progress=sync_in_progress
        )

    except Exception as e:
        logger.error(f"Failed to get sync status: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Failed to retrieve sync status: {str(e)}"
        )
