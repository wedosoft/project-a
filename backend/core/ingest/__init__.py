"""
데이터 수집/처리 모듈

이 모듈은 Freshdesk에서 티켓과 지식베이스 문서를 수집하고 처리하는 기능을 제공합니다.
"""

from .integrator import (
    create_integrated_article_object,
    create_integrated_ticket_object,
)
from .processor import (
    clear_checkpoints,
    ingest,
    load_checkpoint,
    load_local_data,
    save_checkpoint,
    update_status_mappings,
    verify_database_integrity,
)
from .storage import (
    get_integrated_object_from_sqlite,
    sanitize_metadata,
    search_integrated_objects_from_sqlite,
    store_integrated_object_to_sqlite,
)
from .validator import (
    extract_integrated_text_for_embedding,
    extract_integrated_text_for_summary,
    load_status_mappings,
    save_status_mappings,
    validate_integrated_object,
    validate_metadata,
)

__all__ = [
    # integrator
    "create_integrated_article_object",
    "create_integrated_ticket_object",
    # processor
    "clear_checkpoints",
    "ingest",
    "load_checkpoint", 
    "load_local_data",
    "save_checkpoint",
    "update_status_mappings",
    "verify_database_integrity",
    # storage
    "get_integrated_object_from_sqlite",
    "sanitize_metadata",
    "search_integrated_objects_from_sqlite",
    "store_integrated_object_to_sqlite",
    # validator
    "extract_integrated_text_for_embedding",
    "extract_integrated_text_for_summary",
    "load_status_mappings",
    "save_status_mappings",
    "validate_integrated_object",
    "validate_metadata",
]
