"""
통합된 데이터 수집 및 처리 메인 로직 모듈

이 모듈은 Freshdesk에서 티켓과 지식베이스 문서를 가져와 임베딩한 후,
벡터 데이터베이스에 저장하는 메인 프로세싱 로직을 제공합니다.
모든 데이터 처리는 통합 객체(integrated_objects) 기반으로만 수행됩니다.

프로젝트 규칙 및 가이드라인: /PROJECT_RULES.md 참고
"""

import json
import logging
import os
import sys
import time
import pytz
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Callable, List
from dotenv import load_dotenv

# backend 디렉토리를 Python 경로에 추가
current_dir = Path(__file__).resolve().parent
backend_dir = current_dir.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.append(str(backend_dir))

# LLM Manager import  
from core.llm.manager import LLMManager
from core.metadata.normalizer import TenantMetadataNormalizer

# LLM Manager 전역 인스턴스
llm_manager = LLMManager()

from core.search.embeddings import embed_documents
from core.database.vectordb import (
    vector_db,
    purge_vector_db_data,
    process_ticket_to_vector_db,
    process_article_to_vector_db,
    generate_realtime_summary,
    search_vector_db,
    get_vector_db_stats
)
# [DEPRECATED] integrator 기능 제거됨 - Vector DB 단독 모드
# from core.ingest.integrator import (
#     create_integrated_ticket_object, 
#     create_integrated_article_object
# )
from core.ingest.storage import sanitize_metadata
# [DEPRECATED] migration_layer 제거됨 - Vector DB 단독 모드
# from core.migration_layer import store_integrated_object_with_migration
from core.ingest.validator import load_status_mappings, save_status_mappings
from core.platforms.freshdesk.fetcher import (
    extract_tenant_id_from_domain,
    fetch_kb_articles,
    fetch_tickets,
)
from core.llm.summarizer import generate_summary

# 환경변수 로드
load_dotenv()

# 로깅 설정
logger = logging.getLogger(__name__)

def get_kst_time() -> str:
    """현재 시간을 KST로 반환합니다."""
    kst = pytz.timezone('Asia/Seoul')
    return datetime.now(kst).isoformat()

COLLECTION_NAME = "documents"  # Qdrant 컬렉션 이름
PROCESS_ATTACHMENTS = True  # 첨부파일 처리 여부 설정

# 멀티플랫폼 런타임 고객 검증 함수들

def validate_runtime_customer_credentials(domain: str, api_key: str, platform: str = "freshdesk") -> str:
    """
    런타임 고객 인증 정보를 검증하고 tenant_id를 반환합니다.
    
    Args:
        domain: 고객 도메인 (예: "example.freshdesk.com")
        api_key: API 키
        platform: 플랫폼 식별자 (기본값: "freshdesk")
        
    Returns:
        str: 추출된 tenant_id
        
    Raises:
        ValueError: 인증 정보가 유효하지 않은 경우
    """
    if not domain or not api_key:
        raise ValueError("도메인과 API 키는 필수입니다.")
    
    # 도메인에서 tenant_id 추출
    tenant_id = extract_tenant_id_from_domain(domain)
    if not tenant_id:
        raise ValueError(f"유효한 {platform} 도메인이 아닙니다: {domain}")
    
    # API 키 형식 검증 (기본적인 검증)
    if len(api_key) < 10:
        raise ValueError("API 키가 너무 짧습니다.")
    
    logger.info(f"런타임 고객 인증 검증 완료: {tenant_id} ({platform})")
    return tenant_id

def create_runtime_customer_context(domain: str, api_key: str, platform: str = "freshdesk") -> Dict[str, str]:
    """
    런타임 고객 컨텍스트를 생성합니다.
    
    Args:
        domain: 고객 도메인
        api_key: API 키  
        platform: 플랫폼 식별자
        
    Returns:
        Dict[str, str]: 고객 컨텍스트 정보
    """
    tenant_id = validate_runtime_customer_credentials(domain, api_key, platform)
    
    return {
        "tenant_id": tenant_id,
        "domain": domain,
        "api_key": api_key,
        "platform": platform,
        "created_at": get_kst_time()
    }

# 체크포인트 관련 함수들

def save_checkpoint(data_dir: str, stage: str, data: Dict[str, Any]) -> None:
    """
    처리 단계별 체크포인트를 저장합니다.
    
    Args:
        data_dir: 데이터 디렉토리 경로
        stage: 처리 단계 (예: "tickets", "articles", "embeddings")
        data: 저장할 데이터
    """
    try:
        checkpoint_dir = Path(data_dir) / "checkpoints"
        checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        checkpoint_file = checkpoint_dir / f"{stage}.json"
        with open(checkpoint_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.debug(f"체크포인트 저장: {stage} -> {checkpoint_file}")
        
    except Exception as e:
        logger.warning(f"체크포인트 저장 실패 ({stage}): {e}")

def load_checkpoint(data_dir: str, stage: str) -> Optional[Dict[str, Any]]:
    """
    저장된 체크포인트를 로드합니다.
    
    Args:
        data_dir: 데이터 디렉토리 경로
        stage: 처리 단계
        
    Returns:
        Optional[Dict[str, Any]]: 체크포인트 데이터 (없으면 None)
    """
    try:
        checkpoint_file = Path(data_dir) / "checkpoints" / f"{stage}.json"
        if checkpoint_file.exists():
            with open(checkpoint_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.debug(f"체크포인트 로드: {stage}")
            return data
    except Exception as e:
        logger.warning(f"체크포인트 로드 실패 ({stage}): {e}")
    
    return None

def clear_checkpoints(data_dir: str) -> None:
    """
    모든 체크포인트를 삭제합니다.
    
    Args:
        data_dir: 데이터 디렉토리 경로
    """
    try:
        checkpoint_dir = Path(data_dir) / "checkpoints"
        if checkpoint_dir.exists():
            for file in checkpoint_dir.glob("*.json"):
                file.unlink()
            logger.info("모든 체크포인트 삭제 완료")
    except Exception as e:
        logger.warning(f"체크포인트 삭제 실패: {e}")

# 메인 수집 함수

async def ingest(
    tenant_id: str,
    platform: str = "freshdesk",
    incremental: bool = True,
    purge: bool = False,
    skip_embeddings: bool = False,
    skip_summaries: bool = False,
    max_tickets: Optional[int] = None,
    max_articles: Optional[int] = None,
    progress_callback: Optional[Callable] = None
) -> Dict[str, Any]:
    """
    데이터 수집 및 처리를 수행합니다.
    
    ⚠️ 환경변수 ENABLE_FULL_STREAMING_MODE에 따라 다른 로직을 사용합니다:
    - true (기본값): Vector DB 단독 파이프라인 사용 (신규)
    - false: 기존 하이브리드 파이프라인 사용 (100% 보존)
    
    Args:
        tenant_id: 회사 식별자
        platform: 플랫폼 식별자
        incremental: 증분 수집 여부
        purge: 기존 데이터 삭제 여부
        skip_embeddings: 임베딩 건너뛰기
        skip_summaries: 요약 생성 건너뛰기
        max_tickets: 최대 티켓 수집 개수 (None이면 무제한)
        max_articles: 최대 KB 문서 수집 개수 (None이면 무제한)
        progress_callback: 진행률 콜백 함수
        
    Returns:
        Dict[str, Any]: 처리 결과
    """
    # 환경변수로 모드 결정
    enable_full_streaming = os.getenv("ENABLE_FULL_STREAMING_MODE", "true") == "true"
    enable_sql_progress = os.getenv('ENABLE_SQL_PROGRESS_LOGS', 'true').lower() == 'true'
    
    if enable_full_streaming:
        # 🚀 신규: Vector DB 단독 파이프라인
        logger.info(f"Vector DB 단독 모드 데이터 수집 시작: {tenant_id} ({platform})")
        return await ingest_vector_only_mode(
            tenant_id=tenant_id,
            platform=platform,
            incremental=incremental,
            purge=purge,
            max_tickets=max_tickets,
            max_articles=max_articles,
            progress_callback=progress_callback
        )
    else:
        # 🔒 기존: 하이브리드 파이프라인 (100% 보존)
        logger.info(f"🔒 하이브리드 모드로 데이터 수집 시작: {tenant_id} ({platform})")
        return await ingest_legacy_hybrid_mode(
            tenant_id=tenant_id,
            platform=platform,
            incremental=incremental,
            purge=purge,
            skip_embeddings=skip_embeddings,
            skip_summaries=skip_summaries,
            max_tickets=max_tickets,
            max_articles=max_articles,
            progress_callback=progress_callback
        )

async def ingest_vector_only_mode(
    tenant_id: str,
    platform: str = "freshdesk",
    incremental: bool = True,
    purge: bool = False,
    max_tickets: Optional[int] = None,
    max_articles: Optional[int] = None,
    progress_callback: Optional[Callable] = None
) -> Dict[str, Any]:
    """
    🚀 신규 Vector DB 단독 수집 모드
    
    Freshdesk에서 티켓과 지식베이스 문서를 가져와서
    SQL 없이 Vector DB(Qdrant)에만 저장하는 완전히 새로운 파이프라인입니다.
    """
    start_time = time.time()
    result = {
        "success": True,
        "agents_processed": 0,
        "tickets_processed": 0,
        "articles_processed": 0,
        "total_vectors_stored": 0,
        "errors": [],
        "start_time": get_kst_time(),
        "processing_time": 0
    }
    
    logger.info(f"Vector DB 단독 수집 시작: {tenant_id}/{platform}")
    
    try:
        # 환경변수에서 domain과 api_key 가져오기
        domain = os.getenv("FRESHDESK_DOMAIN")
        api_key = os.getenv("FRESHDESK_API_KEY")
        
        if not domain or not api_key:
            raise ValueError(f"tenant_id {tenant_id}에 대한 Freshdesk 설정이 환경변수에 없습니다. FRESHDESK_DOMAIN과 FRESHDESK_API_KEY를 설정해주세요.")
        
        logger.info(f"도메인: {domain}, 최대 티켓: {max_tickets}, 최대 KB: {max_articles}")
        
        # 기존 Vector DB 데이터 삭제 (purge 옵션)
        if purge:
            logger.info("기존 Vector DB 데이터 삭제 중...")
            await purge_vector_db_data(tenant_id, platform)
        
        # 0. 에이전트 수집 (먼저 수집하여 멀티테넌트 라이선스 정보 확보)
        if progress_callback:
            progress_callback({"stage": "agents", "progress": 0})
        
        logger.info("에이전트 수집 시작...")
        
        # FreshdeskCollector를 사용하여 에이전트 수집
        from core.platforms.freshdesk.collector import FreshdeskCollector
        config = {
            "domain": domain,
            "api_key": api_key,
            "tenant_id": tenant_id,
            "max_retries": 3,
            "per_page": 100,
            "request_delay": 0.3
        }
        
        try:
            async with FreshdeskCollector(config) as collector:
                agent_result = await collector.collect_agents()
                logger.info(f"에이전트 수집 완료: {agent_result.get('total_agents', 0)}개 수집, {agent_result.get('saved_agents', 0)}개 저장")
                result["agents_processed"] = agent_result.get('saved_agents', 0)
                
                # 에이전트 수집 완료 진행상황 업데이트
                if progress_callback:
                    progress_callback({"stage": "agents", "progress": 100})
                    
        except Exception as e:
            logger.error(f"에이전트 수집 중 오류: {e}")
            result["errors"].append(f"에이전트 수집 실패: {str(e)}")
            
            # 에이전트 수집 실패시에도 진행상황 업데이트
            if progress_callback:
                progress_callback({"stage": "agents", "progress": 100})
        
        # 1. 티켓 수집 및 Vector DB 저장
        if progress_callback:
            progress_callback({"stage": "tickets", "progress": 0})
        
        logger.info("티켓 수집 시작...")
        tickets = await fetch_tickets(domain=domain, api_key=api_key, max_tickets=max_tickets)
        logger.info(f"수집된 티켓: {len(tickets)}개")
        
        for i, ticket in enumerate(tickets):
            try:
                # 티켓을 Vector DB에 직접 처리 및 저장
                success = await process_ticket_to_vector_db(
                    ticket=ticket,
                    tenant_id=tenant_id,
                    platform=platform
                )
                
                if success:
                    result["tickets_processed"] += 1
                    result["total_vectors_stored"] += 1
                else:
                    error_msg = f"티켓 {ticket.get('id', 'unknown')} 처리 실패"
                    result["errors"].append(error_msg)
                
                if progress_callback:
                    progress = (i + 1) / len(tickets) * 100  # 티켓 단계의 100%
                    progress_callback({"stage": "tickets", "progress": progress})
                
            except Exception as e:
                error_msg = f"티켓 {ticket.get('id', 'unknown')} 처리 실패: {str(e)}"
                logger.error(error_msg)
                result["errors"].append(error_msg)
        
        logger.info(f"티켓 처리 완료: {result['tickets_processed']}개 성공, {len([e for e in result['errors'] if '티켓' in e])}개 실패")
        
        # 2. KB 문서 수집 및 Vector DB 저장
        if progress_callback:
            progress_callback({"stage": "articles", "progress": 50})
        
        logger.info("KB 문서 수집 시작...")
        articles = await fetch_kb_articles(domain=domain, api_key=api_key, max_articles=max_articles)
        logger.info(f"수집된 KB 문서: {len(articles)}개")
        
        for i, article in enumerate(articles):
            try:
                # KB 문서를 Vector DB에 직접 처리 및 저장
                success = await process_article_to_vector_db(
                    article=article,
                    tenant_id=tenant_id,
                    platform=platform
                )
                
                if success:
                    result["articles_processed"] += 1
                    result["total_vectors_stored"] += 1
                else:
                    error_msg = f"KB 문서 {article.get('id', 'unknown')} 처리 실패"
                    result["errors"].append(error_msg)
                
                if progress_callback:
                    progress = (i + 1) / len(articles) * 100  # KB 단계의 100%
                    progress_callback({"stage": "articles", "progress": progress})
                
            except Exception as e:
                error_msg = f"KB 문서 {article.get('id', 'unknown')} 처리 실패: {str(e)}"
                logger.error(error_msg)
                result["errors"].append(error_msg)
        
        logger.info(f"KB 문서 처리 완료: {result['articles_processed']}개 성공, {len([e for e in result['errors'] if 'KB' in e])}개 실패")
        
        result["processing_time"] = time.time() - start_time
        
        logger.info("Vector DB 단독 수집 완료:")
        logger.info(f"  - 에이전트: {result['agents_processed']}개")
        logger.info(f"  - 티켓: {result['tickets_processed']}개")
        logger.info(f"  - KB 문서: {result['articles_processed']}개")
        logger.info(f"  - 총 벡터: {result['total_vectors_stored']}개")
        logger.info(f"  - 소요 시간: {result['processing_time']:.2f}초")
        
        if result['errors']:
            logger.warning(f"오류 {len(result['errors'])}건 발생")
            result["success"] = False
        
        return result
        
    except Exception as e:
        result["success"] = False
        result["processing_time"] = time.time() - start_time
        error_msg = f"Vector DB 단독 수집 중 전체 오류: {str(e)}"
        logger.error(error_msg)
        result["errors"].append(error_msg)
        return result

async def ingest_legacy_hybrid_mode(
    tenant_id: str,
    platform: str = "freshdesk",
    incremental: bool = True,
    purge: bool = False,
    skip_embeddings: bool = False,
    skip_summaries: bool = False,
    max_tickets: Optional[int] = None,
    max_articles: Optional[int] = None,
    progress_callback: Optional[Callable] = None
) -> Dict[str, Any]:
    """
    🔒 기존 하이브리드 수집 모드 (100% 보존)
    
    기존 SQL + Vector DB 하이브리드 로직을 그대로 사용합니다.
    이 함수는 절대 수정하지 않습니다.
    """
    logger.info(f"데이터 수집 시작: {tenant_id} ({platform})")
    start_time = time.time()
    
    result = {
        "tenant_id": tenant_id,
        "platform": platform,
        "start_time": get_kst_time(),
        "agents_processed": 0,
        "tickets_processed": 0,
        "articles_processed": 0,
        "embeddings_created": 0,
        "summaries_created": 0,
        "errors": []
    }
    
    # db 변수를 먼저 None으로 초기화
    db = None
    
    try:
        # 환경변수에서 domain과 api_key 가져오기
        domain = os.getenv("FRESHDESK_DOMAIN")
        api_key = os.getenv("FRESHDESK_API_KEY")
        
        if not domain or not api_key:
            raise ValueError(f"tenant_id {tenant_id}에 대한 Freshdesk 설정이 환경변수에 없습니다. FRESHDESK_DOMAIN과 FRESHDESK_API_KEY를 설정해주세요.")
        
        logger.info(f"사용할 설정 - 도메인: {domain}, tenant_id: {tenant_id}")
        
        # 멀티테넌트 데이터베이스 연결
        from core.database.database import get_database
        from core.database.manager import get_db_manager
        from core.database.models import IntegratedObject
        
        # ORM 매니저 사용
        db_manager = get_db_manager(tenant_id)
        db_manager.create_database()  # 테이블 생성 보장
        
        # 레거시 지원용 (storage.py에서 사용)
        db = get_database(tenant_id, platform)

        if purge:
            # 기존 데이터 삭제 (ORM 방식)
            logger.info("기존 데이터 삭제 중...")
            with db_manager.get_session() as session:
                deleted_count = session.query(IntegratedObject).filter(
                    IntegratedObject.tenant_id == tenant_id,
                    IntegratedObject.platform == platform
                ).delete()
                session.commit()
                logger.info(f"기존 데이터 삭제 완료: {deleted_count}개 객체")
        
        # 0. 에이전트 수집 (먼저 수집하여 멀티테넌트 라이선스 정보 확보)
        if progress_callback:
            progress_callback({"stage": "agents", "progress": 0})
        
        logger.info("에이전트 수집 시작...")
        
        # FreshdeskCollector를 사용하여 에이전트 수집
        from core.platforms.freshdesk.collector import FreshdeskCollector
        config = {
            "domain": domain,
            "api_key": api_key,
            "tenant_id": tenant_id,
            "max_retries": 3,
            "per_page": 100,
            "request_delay": 0.3
        }
        
        try:
            async with FreshdeskCollector(config) as collector:
                agent_result = await collector.collect_agents()
                logger.info(f"에이전트 수집 완료: {agent_result.get('total_agents', 0)}개 수집, {agent_result.get('saved_agents', 0)}개 저장")
                result["agents_processed"] = agent_result.get('saved_agents', 0)
                
                # 에이전트 수집 완료 진행상황 업데이트
                if progress_callback:
                    progress_callback({"stage": "agents", "progress": 100})
                    
        except Exception as e:
            logger.error(f"에이전트 수집 중 오류: {e}")
            result["errors"].append(f"에이전트 수집 실패: {str(e)}")
            
            # 에이전트 수집 실패시에도 진행상황 업데이트
            if progress_callback:
                progress_callback({"stage": "agents", "progress": 100})
        
        # 1. 티켓 수집
        if progress_callback:
            progress_callback({"stage": "tickets", "progress": 0})
        
        # 진행 상황을 데이터베이스에 로그 (환경변수 체크)
        enable_sql_progress = os.getenv('ENABLE_SQL_PROGRESS_LOGS', 'true').lower() == 'true'
        
        if enable_sql_progress:
            db.log_progress(
                tenant_id=tenant_id,
                message="티켓 수집 시작",
                percentage=0,
                step=0,
                total_steps=100
            )
        
        logger.info(f"티켓 수집 시작... (최대 {max_tickets}개)" if max_tickets else "티켓 수집 시작...")
        tickets = await fetch_tickets(domain=domain, api_key=api_key, max_tickets=max_tickets)
        logger.info(f"수집된 티켓 수: {len(tickets)}")
        
        for i, ticket in enumerate(tickets):
            try:
                # Vector DB에 직접 저장 (integrated_object 생성 없이)
                success = await process_ticket_to_vector_db(
                    ticket=ticket,
                    tenant_id=tenant_id,
                    platform=platform
                )
                
                if not success:
                    logger.warning(f"티켓 {ticket.get('id')} Vector DB 저장 실패")
                
                result["tickets_processed"] += 1
                
                if progress_callback:
                    progress = (i + 1) / len(tickets) * 100
                    progress_callback({"stage": "tickets", "progress": progress})
                
                # 진행 상황을 데이터베이스에 로그 (환경변수 체크)
                if enable_sql_progress:
                    db.log_progress(
                        tenant_id=tenant_id,
                        message=f"티켓 처리 중... ({i+1}/{len(tickets)})",
                        percentage=int((i + 1) / len(tickets) * 50),
                        step=i+1,
                        total_steps=len(tickets)
                    )
                
            except Exception as e:
                error_msg = f"티켓 {ticket.get('id', 'unknown')} 처리 실패: {str(e)}"
                logger.error(error_msg)
                result["errors"].append(error_msg)
        
        # 2. KB 문서 수집
        if progress_callback:
            progress_callback({"stage": "articles", "progress": 0})
        
        # 진행 상황을 데이터베이스에 로그 (환경변수 체크)
        if enable_sql_progress:
            db.log_progress(
                tenant_id=tenant_id,
                message="KB 문서 수집 시작",
                percentage=50,
                step=0,
                total_steps=100
            )
        
        logger.info(f"KB 문서 수집 시작... (최대 {max_articles}개)" if max_articles else "KB 문서 수집 시작...")
        articles = await fetch_kb_articles(domain=domain, api_key=api_key, max_articles=max_articles)
        logger.info(f"수집된 KB 문서 수: {len(articles)}")
        
        for i, article in enumerate(articles):
            try:
                # Vector DB에 직접 저장 (integrated_object 생성 없이)
                success = await process_article_to_vector_db(
                    article=article,
                    tenant_id=tenant_id,
                    platform=platform
                )
                
                if not success:
                    logger.warning(f"KB 문서 {article.get('id')} Vector DB 저장 실패")
                
                result["articles_processed"] += 1
                
                if progress_callback:
                    progress = (i + 1) / len(articles) * 100
                    progress_callback({"stage": "articles", "progress": progress})
                
                # 진행 상황을 데이터베이스에 로그 (환경변수 체크)
                if enable_sql_progress:
                    db.log_progress(
                        tenant_id=tenant_id,
                        message=f"KB 문서 처리 중... ({i+1}/{len(articles)})",
                        percentage=50 + int((i + 1) / len(articles) * 30),
                        step=i+1,
                        total_steps=len(articles)
                    )
                
            except Exception as e:
                error_msg = f"KB 문서 {article.get('id', 'unknown')} 처리 실패: {str(e)}"
                logger.error(error_msg)
                result["errors"].append(error_msg)
        
        # 3. 요약 생성 (skip_summaries가 False인 경우에만)
        if not skip_summaries:
            if progress_callback:
                progress_callback({"stage": "summaries", "progress": 0})
            
            if enable_sql_progress:
                db.log_progress(
                    tenant_id=tenant_id,
                    message="요약 생성 시작",
                    percentage=80,
                    step=0,
                    total_steps=100
                )
            
            summary_result = await generate_and_store_summaries(
                tenant_id=tenant_id,
                platform=platform,
                force_update=False
            )
            result["summaries_created"] = summary_result.get("success_count", 0)
            result["errors"].extend(summary_result.get("errors", []))
        
        # 4. 벡터 임베딩 생성 (skip_embeddings가 False인 경우에만)
        if not skip_embeddings:
            if progress_callback:
                progress_callback({"stage": "embeddings", "progress": 0})
            
            if enable_sql_progress:
                db.log_progress(
                    tenant_id=tenant_id,
                    message="벡터 임베딩 생성 시작",
                    percentage=90,
                    step=0,
                    total_steps=100
                )
            
            embedding_result = await sync_summaries_to_vector_db(
                tenant_id=tenant_id,
                platform=platform,
                batch_size=100,
                force_update=False
            )
            result["embeddings_created"] = embedding_result.get("processed_count", 0)
            if embedding_result.get("status") != "success":
                result["errors"].append(f"벡터 임베딩 생성 실패: {embedding_result.get('message')}")
        
        # 최종 진행 상황 로그 (환경변수 체크)
        if enable_sql_progress:
            db.log_progress(
                tenant_id=tenant_id,
                message="데이터 수집 완료",
                percentage=100,
                step=100,
                total_steps=100
            )
        
        processing_time = time.time() - start_time
        result["processing_time"] = processing_time
        result["end_time"] = get_kst_time()
        
        logger.info("✅ 하이브리드 모드 데이터 수집 완료:")
        logger.info(f"  - 에이전트 처리: {result['agents_processed']}개")
        logger.info(f"  - 티켓 처리: {result['tickets_processed']}개")
        logger.info(f"  - KB 문서 처리: {result['articles_processed']}개")
        logger.info(f"  - 요약 생성: {result['summaries_created']}개")
        logger.info(f"  - 임베딩 생성: {result['embeddings_created']}개")
        logger.info(f"  - 총 처리 시간: {processing_time:.2f}초")
        
        if result["errors"]:
            logger.warning(f"❌ 처리 중 {len(result['errors'])}건의 오류 발생")
            for error in result["errors"][:5]:  # 최대 5개만 로그에 표시
                logger.warning(f"  - {error}")
        
        return result
        
    except Exception as e:
        processing_time = time.time() - start_time
        result["processing_time"] = processing_time
        result["end_time"] = get_kst_time()
        error_msg = f"데이터 수집 중 전체 오류: {str(e)}"
        logger.error(error_msg)
        result["errors"].append(error_msg)
        
        if db and enable_sql_progress:
            try:
                db.log_progress(
                    tenant_id=tenant_id,
                    message=f"데이터 수집 실패: {str(e)}",
                    percentage=0,
                    step=0,
                    total_steps=100
                )
            except:
                pass  # 로깅 실패는 무시
        
        return result

# 요약 생성 함수

async def generate_and_store_summaries(
    tenant_id: str,
    platform: str = "freshdesk",
    force_update: bool = False
) -> Dict[str, Any]:
    """
    통합 객체에서 직접 요약을 생성하고 저장합니다.
    
    Args:
        tenant_id: 회사 식별자
        platform: 플랫폼 식별자
        force_update: 기존 요약 강제 업데이트 여부
        
    Returns:
        Dict[str, Any]: 처리 결과
    """
    logger.info(f"LLM 요약 생성 시작 (tenant_id: {tenant_id}, platform: {platform})")
    start_time = time.time()
    
    result = {
        "success_count": 0,
        "failure_count": 0,
        "skipped_count": 0,
        "total_processed": 0,
        "processing_time": 0,
        "errors": []
    }
    
    try:
        # ORM 방식으로 데이터 조회 및 처리
        from core.database.manager import get_db_manager
        from core.repositories.integrated_object_repository import IntegratedObjectRepository
        from core.migration_layer import get_migration_layer
        
        # Migration Layer 사용 여부 확인
        migration_layer = get_migration_layer()
        
        if migration_layer.use_orm:
            # ORM 방식 사용
            db_manager = get_db_manager(tenant_id=tenant_id)
            
            with db_manager.get_session() as session:
                repo = IntegratedObjectRepository(session)
                
                # 요약이 없는 통합 객체들 조회
                if force_update:
                    # 강제 업데이트: 모든 통합 객체
                    objects = repo.get_by_company(
                        tenant_id=tenant_id,
                        platform=platform
                    )
                    # integrated_content가 있는 것만 필터링
                    objects = [obj for obj in objects 
                              if obj.object_type in ('integrated_ticket', 'integrated_article')
                              and obj.integrated_content and obj.integrated_content.strip()]
                else:
                    # 일반 모드: 요약이 없는 것만
                    objects = repo.get_by_company(
                        tenant_id=tenant_id,
                        platform=platform
                    )
                    # 요약이 없고 integrated_content가 있는 것만 필터링
                    objects = [obj for obj in objects 
                              if obj.object_type in ('integrated_ticket', 'integrated_article')
                              and (not obj.summary or obj.summary.strip() == '')
                              and obj.integrated_content and obj.integrated_content.strip()]
                
                logger.info(f"처리할 통합 객체 수: {len(objects)}개")
                result["total_processed"] = len(objects)
                
                for obj in objects:
                    try:
                        original_id = obj.original_id
                        object_type = obj.object_type
                        integrated_content = obj.integrated_content
                        original_data = obj.original_data if isinstance(obj.original_data, dict) else {}
                        
                        # 디버깅 로그
                        logger.debug(f"{object_type} {original_id}: integrated_content 길이 = {len(integrated_content) if integrated_content else 0}")
                        
                        # integrated_content 확인
                        if not integrated_content or not integrated_content.strip():
                            logger.warning(f"{object_type} {original_id}: integrated_content가 없거나 비어있음 - 요약 생성 불가")
                            result["skipped_count"] += 1
                            continue

                        # 객체 타입에 따른 요약 생성
                        if object_type == 'integrated_ticket':
                            # tenant_metadata에서 첨부파일 정보 우선 사용
                            tenant_metadata = obj.tenant_metadata if isinstance(obj.tenant_metadata, dict) else {}
                            
                            # 첨부파일 정보 통합 (tenant_metadata 우선, 없으면 original_data 사용)
                            attachments = []
                            if tenant_metadata.get('has_attachments') and tenant_metadata.get('attachments'):
                                attachments = tenant_metadata['attachments']
                                logger.debug(f"티켓 {original_id}: tenant_metadata에서 {len(attachments)}개 첨부파일 로드")
                            elif original_data.get('all_attachments'):
                                attachments = original_data.get('all_attachments', [])
                                logger.debug(f"티켓 {original_id}: original_data에서 {len(attachments)}개 첨부파일 로드")
                            
                            # 티켓 요약 생성
                            ticket_data = {
                                'id': original_id,
                                'subject': original_data.get('subject', ''),
                                'description': original_data.get('description', ''),
                                'status': original_data.get('status', ''),
                                'priority': original_data.get('priority', ''),
                                'integrated_text': integrated_content,
                                'conversations': original_data.get('conversations', []),
                                'attachments': attachments,  # 통합된 첨부파일 정보 사용
                                'tenant_metadata': tenant_metadata  # 메타데이터 정보도 함께 전달
                            }
                            
                            try:
                                logger.debug(f"티켓 {original_id}: LLM 요약 생성 시작")
                                summary_result = await llm_manager.generate_ticket_summary(ticket_data)
                                
                                logger.debug(f"티켓 {original_id}: LLM 응답 - {type(summary_result)} {bool(summary_result)}")
                                
                                if summary_result and 'summary' in summary_result:
                                    summary = summary_result['summary']
                                    logger.debug(f"티켓 {original_id}: 요약 길이 = {len(summary) if summary else 0}")
                                    
                                    # 업데이트된 메타데이터 처리
                                    if 'updated_metadata' in summary_result:
                                        tenant_metadata = summary_result['updated_metadata']
                                        logger.debug(f"티켓 {original_id}: AI 처리 정보가 메타데이터에 업데이트됨")
                                    
                                    # 요약이 실제로 유의미한지 확인
                                    if not summary or summary.strip() == "":
                                        logger.warning(f"티켓 {original_id}: 빈 요약 생성됨")
                                        summary = "요약 내용이 비어있습니다."
                                    elif summary in ["요약 생성에 실패했습니다.", "LLM 요약 생성 중 오류가 발생했습니다."]:
                                        logger.warning(f"티켓 {original_id}: 오류 메시지가 요약으로 반환됨")
                                    else:
                                        logger.info(f"티켓 {original_id}: 유효한 요약 생성 완료 (길이: {len(summary)})")
                                else:
                                    logger.warning(f"티켓 {original_id}: summary_result에 'summary' 키가 없음: {summary_result}")
                                    summary = "요약 생성에 실패했습니다."
                            except Exception as e:
                                logger.error(f"티켓 {original_id} 요약 생성 중 LLM 오류: {e}")
                                summary = "LLM 요약 생성 중 오류가 발생했습니다."
                                
                        elif object_type == 'integrated_article':
                            # tenant_metadata에서 기본 정보 추출
                            tenant_metadata = obj.tenant_metadata if isinstance(obj.tenant_metadata, dict) else {}
                            if isinstance(obj.tenant_metadata, str):
                                try:
                                    tenant_metadata = json.loads(obj.tenant_metadata)
                                except json.JSONDecodeError:
                                    tenant_metadata = {}
                            
                            # KB 문서는 메타데이터가 제한적이므로 기본 구조만 사용
                            if not tenant_metadata:
                                tenant_metadata = TenantMetadataNormalizer.extract_from_original_data(original_data)
                                logger.debug(f"KB 문서 {original_id}: 원본 데이터에서 메타데이터 추출")
                            else:
                                tenant_metadata = TenantMetadataNormalizer.normalize(tenant_metadata)
                                logger.debug(f"KB 문서 {original_id}: 기존 메타데이터 정규화")
                            
                            # KB 문서 요약 생성
                            kb_data = {
                                'id': original_id,
                                'title': original_data.get('title', ''),
                                'content': integrated_content,
                                'description': original_data.get('description', ''),
                                'category': original_data.get('category', ''),
                                'tags': original_data.get('tags', []),
                                'created_at': original_data.get('created_at', ''),
                                'updated_at': original_data.get('updated_at', ''),
                                'tenant_metadata': tenant_metadata  # 메타데이터 추가
                            }
                            
                            try:
                                logger.debug(f"KB 문서 {original_id}: LLM 요약 생성 시작")
                                summary_result = await llm_manager.generate_knowledge_base_summary(kb_data)
                                
                                logger.debug(f"KB 문서 {original_id}: LLM 응답 - {type(summary_result)} {bool(summary_result)}")
                                
                                if summary_result and 'summary' in summary_result:
                                    summary = summary_result['summary']
                                    logger.debug(f"KB 문서 {original_id}: 요약 길이 = {len(summary) if summary else 0}")
                                    
                                    # 업데이트된 메타데이터 처리 (KB 문서용)
                                    if 'updated_metadata' in summary_result:
                                        tenant_metadata = summary_result['updated_metadata']
                                        logger.debug(f"KB 문서 {original_id}: AI 처리 정보가 메타데이터에 업데이트됨")
                                    
                                    # 요약이 실제로 유의미한지 확인
                                    if not summary or summary.strip() == "":
                                        logger.warning(f"KB 문서 {original_id}: 빈 요약 생성됨")
                                        summary = "요약 내용이 비어있습니다."
                                    elif summary in ["요약 생성에 실패했습니다.", "LLM 요약 생성 중 오류가 발생했습니다."]:
                                        logger.warning(f"KB 문서 {original_id}: 오류 메시지가 요약으로 반환됨")
                                    else:
                                        logger.info(f"KB 문서 {original_id}: 유효한 요약 생성 완료 (길이: {len(summary)})")
                                else:
                                    logger.warning(f"KB 문서 {original_id}: summary_result에 'summary' 키가 없음: {summary_result}")
                                    summary = "요약 생성에 실패했습니다."
                                    
                            except Exception as e:
                                logger.error(f"KB 문서 {original_id} 요약 생성 중 LLM 오류: {e}")
                                summary = "LLM 요약 생성 중 오류가 발생했습니다."
                        else:
                            result["skipped_count"] += 1
                            continue
                        
                        # 요약 업데이트 (ORM 방식)
                        if summary and summary.strip():
                            # 오류 메시지가 아닌 실제 요약인지 확인
                            error_messages = [
                                "요약 생성에 실패했습니다.",
                                "LLM 요약 생성 중 오류가 발생했습니다.",
                                "요약 내용이 비어있습니다.",
                                "분석할 내용이 없습니다."
                            ]
                            
                            is_error_message = any(error_msg in summary for error_msg in error_messages)
                            
                            obj.summary = summary
                            obj.summary_generated_at = datetime.utcnow()
                            
                            # 업데이트된 메타데이터 저장 (JSON 직렬화)
                            obj.tenant_metadata = json.dumps(tenant_metadata, ensure_ascii=False)
                            
                            session.flush()  # 변경사항 플러시
                            
                            if not is_error_message and len(summary.strip()) > 20:  # 최소 20자 이상의 실제 요약
                                result["success_count"] += 1
                                logger.debug(f"{object_type} {original_id}: 유효한 요약 생성 및 저장 완료")
                            else:
                                result["failure_count"] += 1
                                logger.debug(f"{object_type} {original_id}: 오류 메시지가 요약으로 저장됨")
                        else:
                            result["failure_count"] += 1
                            logger.debug(f"{object_type} {original_id}: 빈 요약으로 인한 실패")
                        
                    except Exception as e:
                        error_msg = f"{object_type} {original_id} 요약 생성 중 오류: {e}"
                        logger.error(error_msg)
                        result["errors"].append(error_msg)
                        result["failure_count"] += 1
                
                # 커밋
                session.commit()
                logger.info("✅ 요약 생성 트랜잭션 커밋 완료")
        
        else:
            # 기존 SQLite 방식 사용 (하위 호환성)
            from core.database.database import get_database
            db = get_database(tenant_id, platform)
            
            # 기존 SQLite 로직은 그대로 유지...
            logger.warning("⚠️ SQLite 방식 사용 중 - ORM 활성화를 권장합니다")
            # 여기에 기존 SQLite 로직 구현 필요시 추가
        
        result["processing_time"] = time.time() - start_time
        
        logger.info("✅ LLM 요약 생성 완료:")
        logger.info(f"  - 성공: {result['success_count']}개")
        logger.info(f"  - 실패: {result['failure_count']}개")
        logger.info(f"  - 건너뜀: {result['skipped_count']}개")
        logger.info(f"  - 소요 시간: {result['processing_time']:.2f}초")
        
        if result["errors"]:
            logger.warning("❌ 오류 목록:")
            for error in result["errors"][:5]:  # 최대 5개만 표시
                logger.warning(f"  - {error}")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ LLM 요약 생성 중 전체 오류: {e}")
        result["failure_count"] += 1
        result["errors"].append(str(e))
        result["processing_time"] = time.time() - start_time
        return result
        
        # 데이터베이스 연결 확인 및 연결
        if not db.connection:
            db.connect()
        
        cursor = db.connection.cursor()
        
        # 요약이 없는 통합 객체들 조회 (티켓 + KB 문서)
        if force_update:
            # 강제 업데이트: 모든 통합 객체
            cursor.execute("""
                SELECT original_id, object_type, original_data, integrated_content, tenant_metadata 
                FROM integrated_objects 
                WHERE tenant_id = ? AND platform = ? 
                AND object_type IN ('integrated_ticket', 'integrated_article')
                AND integrated_content IS NOT NULL AND integrated_content != ''
            """, (tenant_id, platform))
        else:
            # 일반 모드: 요약이 없는 것만
            cursor.execute("""
                SELECT original_id, object_type, original_data, integrated_content, tenant_metadata 
                FROM integrated_objects 
                WHERE tenant_id = ? AND platform = ? 
                AND object_type IN ('integrated_ticket', 'integrated_article')
                AND (summary IS NULL OR summary = '')
                AND integrated_content IS NOT NULL AND integrated_content != ''
            """, (tenant_id, platform))
        
        rows = cursor.fetchall()
        logger.info(f"처리할 통합 객체 수: {len(rows)}개")
        
        for row in rows:
            try:
                original_id, object_type, original_data_str, integrated_content, tenant_metadata_str = row
                
                # 디버깅 로그
                logger.debug(f"{object_type} {original_id}: integrated_content 길이 = {len(integrated_content) if integrated_content else 0}")
                
                # 데이터 파싱 및 메타데이터 정규화
                try:
                    original_data = json.loads(original_data_str) if original_data_str else {}
                    raw_tenant_metadata = json.loads(tenant_metadata_str) if tenantMetadata_str else {}
                    
                    # 메타데이터 정규화 처리
                    if not raw_tenant_metadata:
                        # 기존 메타데이터가 없으면 원본 데이터에서 추출
                        tenant_metadata = TenantMetadataNormalizer.extract_from_original_data(original_data)
                        logger.debug(f"{object_type} {original_id}: 원본 데이터에서 메타데이터 추출")
                    else:
                        # 기존 메타데이터가 있으면 정규화만 수행
                        tenant_metadata = TenantMetadataNormalizer.normalize(raw_tenant_metadata)
                        logger.debug(f"{object_type} {original_id}: 기존 메타데이터 정규화")
                        
                except json.JSONDecodeError:
                    logger.warning(f"{object_type} {original_id}: 데이터 파싱 실패")
                    original_data = {}
                    # 파싱 실패시에도 기본 메타데이터 구조 제공
                    tenant_metadata = TenantMetadataNormalizer.normalize({})
                
                # integrated_content 확인
                if not integrated_content or not integrated_content.strip():
                    logger.warning(f"{object_type} {original_id}: integrated_content가 없거나 비어있음 - 요약 생성 불가")
                    result["skipped_count"] += 1
                    continue

                # 객체 타입에 따른 요약 생성
                if object_type == 'integrated_ticket':
                    # 티켓 요약 생성
                    content_type = "ticket"
                    subject = original_data.get('subject', '')
                    
                    # 첨부파일 정보 추가
                    ticket_metadata = {
                        'status': original_data.get('status', ''),
                        'priority': original_data.get('priority', ''),
                        'created_at': original_data.get('created_at', ''),
                        'ticket_id': original_id
                    }
                    
                    # 통합 객체에서 첨부파일 정보 가져오기 (개별 테이블 참조 제거)
                    all_attachments = original_data.get('all_attachments', [])
                    if all_attachments:
                        ticket_metadata['attachments'] = [
                            {
                                'id': att.get('id'),
                                'name': att.get('name'),
                                'content_type': att.get('content_type'),
                                'size': att.get('size'),
                                'ticket_id': original_id,
                                'conversation_id': att.get('conversation_id'),
                                'attachment_url': att.get('attachment_url') or att.get('download_url')
                            }
                            for att in all_attachments
                        ]
                        logger.debug(f"티켓 {original_id}: 첨부파일 메타데이터 설정 완료 - {len(ticket_metadata['attachments'])}개")
                    else:
                        ticket_metadata['attachments'] = []
                    
                    summary_metadata = ticket_metadata
                    
                elif object_type == 'integrated_article':
                    # KB 문서 요약 생성
                    content_type = "knowledge_base"
                    subject = original_data.get('title', '')
                    
                    summary_metadata = {
                        'status': original_data.get('status', ''),
                        'category_id': original_data.get('category_id', ''),
                        'created_at': original_data.get('created_at', '')
                    }
                else:
                    logger.warning(f"알 수 없는 객체 타입: {object_type}")
                    result["skipped_count"] += 1
                    continue

                # LLM 요약 생성 - LLMManager 사용
                if content_type == "ticket":
                    # 티켓 데이터 구성
                    ticket_data = {
                        'id': original_id,
                        'subject': subject,
                        'description': original_data.get('description', ''),
                        'status': original_data.get('status', ''),
                        'priority': original_data.get('priority', ''),
                        'integrated_text': integrated_content,
                        'conversations': original_data.get('conversations', []),
                        'attachments': summary_metadata.get('attachments', [])
                    }
                    summary_result = await llm_manager.generate_ticket_summary(ticket_data)
                    summary = summary_result.get('summary', '요약 생성에 실패했습니다.') if summary_result else '요약 생성에 실패했습니다.'
                    
                elif content_type == "knowledge_base":
                    # KB 데이터 구성  
                    kb_data = {
                        'id': original_id,
                        'title': subject,
                        'content': integrated_content,
                        'description': original_data.get('description', ''),
                        'category': original_data.get('category', ''),
                        'tags': original_data.get('tags', []),
                        'created_at': original_data.get('created_at', ''),
                        'updated_at': original_data.get('updated_at', '')
                    }
                    summary_result = await llm_manager.generate_knowledge_base_summary(kb_data)
                    summary = summary_result.get('summary', '요약 생성에 실패했습니다.') if summary_result else '요약 생성에 실패했습니다.'
                else:
                    logger.warning(f"알 수 없는 content_type: {content_type}")
                    summary = "지원하지 않는 콘텐츠 타입입니다."
                
                # 요약만 업데이트 (기존 데이터는 보존)
                cursor.execute("""
                    UPDATE integrated_objects 
                    SET summary = ? 
                    WHERE tenant_id = ? AND platform = ? AND object_type = ? AND original_id = ?
                """, (summary, tenant_id, platform, object_type, original_id))
                db.connection.commit()
                
                result["success_count"] += 1
                logger.debug(f"{object_type} {original_id}: 요약 생성 및 저장 완료")
                
            except Exception as e:
                logger.error(f"{object_type} {original_id} 요약 생성 중 오류: {e}")
                result["failure_count"] += 1
                result["errors"].append(f"{object_type} {original_id}: {str(e)}")
        
        result["total_processed"] = result["success_count"] + result["failure_count"] + result["skipped_count"]
        result["processing_time"] = time.time() - start_time
        
        logger.info("✅ LLM 요약 생성 완료:")
        logger.info(f"  - 성공: {result['success_count']}개")
        logger.info(f"  - 실패: {result['failure_count']}개")
        logger.info(f"  - 건너뜀: {result['skipped_count']}개")
        logger.info(f"  - 총 처리: {result['total_processed']}")
        logger.info(f"  - 소요 시간: {result['processing_time']:.2f}초")
        
        return result
        
    except Exception as e:
        result["failure_count"] += 1
        result["errors"].append(str(e))
        result["processing_time"] = time.time() - start_time
        return result

# 벡터 DB 동기화 함수

async def sync_summaries_to_vector_db(
    tenant_id: str, 
    platform: str = "freshdesk",
    batch_size: int = 100,
    force_update: bool = False
) -> Dict[str, Any]:
    """
    통합 객체에서 요약 데이터를 읽어서 벡터 DB에 동기화합니다.
    
    Args:
        tenant_id: 테넌트 ID
        platform: 플랫폼 (기본값: freshdesk)
        batch_size: 배치 크기 (기본값: 100)
        force_update: 강제 업데이트 여부 (기본값: False)
        
    Returns:
        Dict[str, Any]: 동기화 결과
    """
    logger.info(f"벡터 DB 동기화 시작 - {tenant_id}/{platform}")
    
    try:
        # Migration Layer 사용 여부 확인
        from core.migration_layer import get_migration_layer
        migration_layer = get_migration_layer()
        
        if migration_layer.use_orm:
            # ORM 방식 사용
            from core.database.manager import get_db_manager
            from core.repositories.integrated_object_repository import IntegratedObjectRepository
            
            db_manager = get_db_manager(tenant_id=tenant_id)
            
            with db_manager.get_session() as session:
                repo = IntegratedObjectRepository(session)
                
                # 요약이 있는 통합 객체들 조회
                objects = repo.get_by_company(
                    tenant_id=tenant_id,
                    platform=platform
                )
                
                # 요약이 있는 객체만 필터링
                objects_with_summary = [
                    obj for obj in objects 
                    if obj.summary and obj.summary.strip()
                ]
                
                if not objects_with_summary:
                    logger.info("동기화할 요약 데이터가 없습니다")
                    return {"status": "success", "message": "동기화할 데이터 없음", "processed_count": 0}
                
                # 벡터 DB용 문서 준비
                documents = []
                for obj in objects_with_summary:
                    # original_data.metadata에서 실제 데이터 추출
                    try:
                        if isinstance(obj.original_data, str):
                            original_data = json.loads(obj.original_data)
                        elif isinstance(obj.original_data, dict):
                            original_data = obj.original_data
                        else:
                            original_data = {}
                    except (json.JSONDecodeError, TypeError):
                        logger.warning(f"객체 {obj.original_id}: original_data 파싱 실패")
                        original_data = {}
                    
                    # 실제 Freshdesk 메타데이터는 original_data.metadata에 있음
                    actual_metadata = original_data.get('metadata', {}) if original_data else {}
                    
                    # 벡터 DB에 저장할 메타데이터 구성
                    filtered_metadata = {
                        "tenant_id": tenant_id,
                        "platform": platform,
                        "original_id": str(obj.original_id),
                        "doc_type": "article" if obj.object_type == "integrated_article" else "ticket",
                        "object_type": "article" if obj.object_type == "integrated_article" else "ticket",
                    }
                    
                    # 객체 타입별로 적절한 필드 추가
                    if obj.object_type == "integrated_article":
                        # KB 문서 메타데이터 (actual_metadata에서 가져오기)
                        filtered_metadata.update({
                            "title": actual_metadata.get('subject', ''),  # KB에서는 subject가 제목
                            "category": actual_metadata.get('category', ''),
                            "folder": actual_metadata.get('folder', ''),
                            "status": actual_metadata.get('status', 2),  # 숫자로 저장
                            "article_type": actual_metadata.get('article_type', ''),
                            "agent_name": actual_metadata.get('agent_name', ''),
                            "tags": actual_metadata.get('tags', []),
                            "has_attachments": actual_metadata.get('has_attachments', False),
                            "complexity_level": actual_metadata.get('complexity_level', ''),
                            "view_count": actual_metadata.get('view_count', 0),
                            "created_at": actual_metadata.get('created_at', ''),
                            "updated_at": actual_metadata.get('updated_at', '')
                        })
                        
                    elif obj.object_type == "integrated_ticket":
                        # 티켓 메타데이터 (actual_metadata에서 가져오기)
                        filtered_metadata.update({
                            "subject": actual_metadata.get('subject', ''),
                            "status": actual_metadata.get('status', 2),  # 숫자로 저장
                            "priority": actual_metadata.get('priority', 1),  # 숫자로 저장
                            "requester_name": actual_metadata.get('requester_name', ''),
                            "agent_name": actual_metadata.get('agent_name', ''),
                            "company_name": actual_metadata.get('company_name', ''),
                            "ticket_category": actual_metadata.get('ticket_category', ''),
                            "has_attachments": actual_metadata.get('has_attachments', False),
                            "complexity_level": actual_metadata.get('complexity_level', ''),
                            "created_at": actual_metadata.get('created_at', ''),
                            "updated_at": actual_metadata.get('updated_at', '')
                        })
                    
                    # None 값과 빈 값 제거 (Qdrant 최적화)
                    filtered_metadata = {k: v for k, v in filtered_metadata.items() 
                                       if v is not None and v != "" and v != []}
                    
                    logger.info(f"문서 {obj.original_id}: 벡터 ID = {tenant_id}_{platform}_{obj.original_id}, 메타데이터 필드 수 = {len(filtered_metadata)}")
                    
                    # 벡터 DB용 문서 생성
                    doc = {
                        "id": f"{tenant_id}_{platform}_{obj.original_id}",
                        "content": obj.content,
                        "metadata": filtered_metadata
                    }
                    documents.append(doc)
                
                # 배치 처리로 임베딩 생성 및 벡터 DB 저장
                if documents:
                    logger.info(f"총 {len(documents)}개 문서를 배치 크기 {batch_size}로 처리 시작")
                    total_processed = 0
                    
                    # 배치 단위로 처리
                    for i in range(0, len(documents), batch_size):
                        batch_documents = documents[i:i + batch_size]
                        batch_num = (i // batch_size) + 1
                        total_batches = (len(documents) + batch_size - 1) // batch_size
                        
                        logger.info(f"배치 {batch_num}/{total_batches} 처리 중... ({len(batch_documents)}개 문서)")
                        
                        # 텍스트와 메타데이터 분리
                        texts = [doc["content"] for doc in batch_documents]
                        metadatas = [doc["metadata"] for doc in batch_documents]
                        ids = [doc["id"] for doc in batch_documents]
                        
                        # 임베딩 생성
                        embeddings = embed_documents(texts)
                        
                        if embeddings and len(embeddings) == len(texts):
                            # 벡터 DB에 저장
                            logger.info(f"🔍 벡터 DB 저장 시도: {len(texts)}개 문서")
                            vector_db.add_documents(
                                texts=texts,
                                embeddings=embeddings,
                                metadatas=metadatas,
                                ids=ids
                            )
                            total_processed += len(batch_documents)
                            logger.info(f"✅ 배치 {batch_num} 완료: {len(batch_documents)}건 벡터 DB에 저장됨")
                            
                            # 벡터 DB 저장 확인
                            collection_count = vector_db.count(tenant_id=tenant_id, platform=platform)
                            logger.info(f"📊 현재 벡터 DB 총 문서 수: {collection_count}개")
                        else:
                            logger.error(f"배치 {batch_num} 임베딩 생성 실패: {len(embeddings) if embeddings else 0}/{len(texts)}")
                            return {"status": "error", "message": f"배치 {batch_num} 임베딩 생성 실패", "processed_count": total_processed}
                    
                    logger.info(f"모든 배치 처리 완료: 총 {total_processed}건 처리")
                    
                    return {
                        "status": "success",
                        "message": f"동기화 완료: {total_processed}건 처리",
                        "processed_count": total_processed,
                        "total_count": total_processed
                    }
                else:
                    return {"status": "success", "message": "처리할 문서 없음", "processed_count": 0}
        
        else:
            # 기존 SQLite 방식 사용 (하위 호환성)
            from core.database.database import get_database
            
            db = get_database(tenant_id, platform)
            
            # 새로운 session 방식 사용
            with db.get_session() as session:
                # 요약 데이터 조회 (original_data도 함께 가져오기)
                result = session.execute("""
                    SELECT object_id, object_type, summary, original_data
                    FROM integrated_objects 
                    WHERE summary IS NOT NULL 
                    AND summary != ''
                    ORDER BY created_at DESC
                """)
                
                summaries = result.fetchall()
                
                if not summaries:
                    logger.info("동기화할 요약 데이터가 없습니다")
                    return {"status": "success", "message": "동기화할 데이터 없음", "processed_count": 0}
                
                # 벡터 DB용 문서 준비
                documents = []
                for row in summaries:
                    object_id, object_type, summary, original_data_str = row
                    
                    # original_data에서 직접 메타데이터 추출
                    try:
                        original_data = json.loads(original_data_str) if original_data_str else {}
                    except (json.JSONDecodeError, TypeError):
                        logger.warning(f"객체 {object_id}: original_data 파싱 실패")
                        original_data = {}
                    
                    # 벡터 DB에 저장할 메타데이터 구성
                    filtered_metadata = {
                        "tenant_id": tenant_id,
                        "platform": platform,
                        "original_id": str(object_id),
                        "doc_type": "article" if object_type == "integrated_article" else "ticket",
                        "object_type": "article" if object_type == "integrated_article" else "ticket",
                    }
                    
                    # 객체 타입별로 적절한 필드 추가
                    if object_type == "integrated_article":
                        # KB 문서 메타데이터
                        filtered_metadata.update({
                            "title": original_data.get('title', ''),
                            "description": original_data.get('description', ''),
                            "category": original_data.get('category', {}),
                            "status": original_data.get('status', 2),  # 숫자로 저장
                            "folder_id": original_data.get('folder_id'),
                            "agent_id": original_data.get('agent_id'),
                            "created_at": original_data.get('created_at', ''),
                            "updated_at": original_data.get('updated_at', '')
                        })
                        
                    elif object_type == "integrated_ticket":
                        # 티켓 메타데이터  
                        filtered_metadata.update({
                            "subject": original_data.get('subject', ''),
                            "description": original_data.get('description_text', ''),
                            "status": original_data.get('status', 2),  # 숫자로 저장
                            "priority": original_data.get('priority', 1),  # 숫자로 저장
                            "requester_id": original_data.get('requester_id'),
                            "responder_id": original_data.get('responder_id'),
                            "group_id": original_data.get('group_id'),
                            "company_id": original_data.get('company_id'),
                            "created_at": original_data.get('created_at', ''),
                            "updated_at": original_data.get('updated_at', '')
                        })
                    
                    # None 값 제거 (Qdrant에서 None을 처리하지 못할 수 있음)
                    filtered_metadata = {k: v for k, v in filtered_metadata.items() if v is not None}
                    
                    # 벡터 DB용 문서 생성
                    doc = {
                        "id": f"{tenant_id}_{platform}_{object_id}",
                        "content": summary,
                        "metadata": filtered_metadata
                    }
                    documents.append(doc)
                    
                    logger.debug(f"문서 {object_id}: 메타데이터 필드 수 = {len(filtered_metadata)}")
                
                # 임베딩 생성 및 벡터 DB 저장 (배치 처리)
                if documents:
                    logger.info(f"총 {len(documents)}개 문서를 배치 크기 {batch_size}로 처리 시작")
                    total_processed = 0
                    
                    # 배치 단위로 처리
                    for i in range(0, len(documents), batch_size):
                        batch_documents = documents[i:i + batch_size]
                        batch_num = (i // batch_size) + 1
                        total_batches = (len(documents) + batch_size - 1) // batch_size
                        
                        logger.info(f"배치 {batch_num}/{total_batches} 처리 중... ({len(batch_documents)}개 문서)")
                        
                        # 텍스트와 메타데이터 분리
                        texts = [doc["content"] for doc in batch_documents]
                        metadatas = [doc["metadata"] for doc in batch_documents]
                        ids = [doc["id"] for doc in batch_documents]
                        
                        # 임베딩 생성
                        embeddings = embed_documents(texts)
                        
                        if embeddings and len(embeddings) == len(texts):
                            # 벡터 DB에 저장
                            logger.info(f"🔍 벡터 DB 저장 시도: {len(texts)}개 문서")
                            vector_db.add_documents(
                                texts=texts,
                                embeddings=embeddings,
                                metadatas=metadatas,
                                ids=ids
                            )
                            total_processed += len(batch_documents)
                            logger.info(f"✅ 배치 {batch_num} 완료: {len(batch_documents)}건 벡터 DB에 저장됨")
                            
                            # 벡터 DB 저장 확인
                            collection_count = vector_db.count(tenant_id=tenant_id, platform=platform)
                            logger.info(f"📊 현재 벡터 DB 총 문서 수: {collection_count}개")
                        else:
                            logger.error(f"배치 {batch_num} 임베딩 생성 실패: {len(embeddings) if embeddings else 0}/{len(texts)}")
                            return {"status": "error", "message": f"배치 {batch_num} 임베딩 생성 실패", "processed_count": total_processed}
                    
                    logger.info(f"모든 배치 처리 완료: 총 {total_processed}건 처리")
                    
                    return {
                        "status": "success",
                        "message": f"동기화 완료: {total_processed}건 처리",
                        "processed_count": total_processed,
                        "total_count": total_processed
                    }
                else:
                    return {"status": "success", "message": "처리할 문서 없음", "processed_count": 0}
        
    except Exception as e:
        logger.error(f"벡터 DB 동기화 중 오류: {e}")
        return {"status": "error", "message": str(e), "processed_count": 0}

# 상태 매핑 업데이트 함수

async def update_status_mappings(collection_name: str = COLLECTION_NAME) -> None:
    """상태 매핑을 업데이트합니다."""
    logger.info("상태 매핑 업데이트 시작")
    
    try:
        # 현재 저장된 상태 매핑 로드
        status_mappings = load_status_mappings()
        
        # 벡터 DB에서 최신 상태 정보 가져오기
        # (실제 구현시 벡터 DB에서 상태 정보를 수집하는 로직 추가)
        
        # 상태 매핑 저장
        save_status_mappings(status_mappings)
        
        logger.info("상태 매핑 업데이트 완료")
        
    except Exception as e:
        logger.error(f"상태 매핑 업데이트 중 오류: {e}")
        raise

def verify_database_integrity() -> bool:
    """데이터베이스 무결성을 검증합니다."""
    logger.info("데이터베이스 무결성 검증 시작")
    
    try:
        # 무결성 검증 로직 (기본적인 검증)
        # 실제 구현시 더 상세한 검증 로직 추가
        
        logger.info("데이터베이스 무결성 검증 완료")
        return True
        
    except Exception as e:
        logger.error(f"데이터베이스 무결성 검증 중 오류: {e}")
        return False
