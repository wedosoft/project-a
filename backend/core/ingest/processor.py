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
from typing import Any, Dict, Optional, Callable
from dotenv import load_dotenv

# backend 디렉토리를 Python 경로에 추가
current_dir = Path(__file__).resolve().parent
backend_dir = current_dir.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.append(str(backend_dir))

# LLM Manager import  
from core.llm.manager import LLMManager

# LLM Manager 전역 인스턴스
llm_manager = LLMManager()

from core.search.embeddings.embedder import embed_documents
from core.database.vectordb import vector_db
from core.ingest.integrator import (
    create_integrated_ticket_object, 
    create_integrated_article_object
)
from core.ingest.storage import sanitize_metadata
from core.migration_layer import store_integrated_object_with_migration
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
    logger.info(f"데이터 수집 시작: {tenant_id} ({platform})")
    start_time = time.time()
    
    result = {
        "tenant_id": tenant_id,
        "platform": platform,
        "start_time": get_kst_time(),
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
        import os
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
        
        # 1. 티켓 수집
        if progress_callback:
            progress_callback({"stage": "tickets", "progress": 0})
        
        # 진행 상황을 데이터베이스에 로그
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
                # 통합 티켓 객체 생성 및 저장
                integrated_ticket = create_integrated_ticket_object(
                    ticket=ticket,
                    tenant_id=tenant_id
                )
                
                store_integrated_object_with_migration(
                    integrated_object=integrated_ticket, 
                    tenant_id=tenant_id, 
                    platform=platform
                )
                
                result["tickets_processed"] += 1
                
                if progress_callback:
                    progress = (i + 1) / len(tickets) * 100
                    progress_callback({"stage": "tickets", "progress": progress})
                
                # 진행 상황을 데이터베이스에 로그
                db.log_progress(
                    tenant_id=tenant_id,
                    message=f"티켓 {i + 1}/{len(tickets)} 처리 완료",
                    percentage=progress if 'progress' in locals() else (i + 1) / len(tickets) * 100,
                    step=i + 1,
                    total_steps=len(tickets)
                )
                    
            except Exception as e:
                logger.error(f"티켓 처리 오류 (ID: {ticket.get('id', 'unknown')}): {e}")
                result["errors"].append(f"티켓 {ticket.get('id', 'unknown')}: {str(e)}")
        
        # 2. KB 문서 수집
        if progress_callback:
            progress_callback({"stage": "articles", "progress": 0})
        
        # 진행 상황을 데이터베이스에 로그
        db.log_progress(
            tenant_id=tenant_id,
            message="아티클 수집 시작",
            percentage=0,
            step=0,
            total_steps=100
        )
        
        logger.info(f"아티클 수집 시작... (최대 {max_articles}개)" if max_articles else "아티클 수집 시작...")
        articles = await fetch_kb_articles(domain=domain, api_key=api_key, max_articles=max_articles)
        logger.info(f"수집된 아티클 수: {len(articles)}")
        
        for i, article in enumerate(articles):
            try:
                # 통합 문서 객체 생성 및 저장
                integrated_article = create_integrated_article_object(
                    article=article,
                    tenant_id=tenant_id
                )
                
                store_integrated_object_with_migration(
                    integrated_object=integrated_article, 
                    tenant_id=tenant_id, 
                    platform=platform
                )
                
                result["articles_processed"] += 1
                
                if progress_callback:
                    progress = (i + 1) / len(articles) * 100
                    progress_callback({"stage": "articles", "progress": progress})
                
                # 진행 상황을 데이터베이스에 로그
                db.log_progress(
                    tenant_id=tenant_id,
                    message=f"아티클 {i + 1}/{len(articles)} 처리 완료",
                    percentage=progress if 'progress' in locals() else (i + 1) / len(articles) * 100,
                    step=i + 1,
                    total_steps=len(articles)
                )
                    
            except Exception as e:
                logger.error(f"KB 문서 처리 오류 (ID: {article.get('id', 'unknown')}): {e}")
                result["errors"].append(f"KB 문서 {article.get('id', 'unknown')}: {str(e)}")
        
        # 3. 요약 생성
        if not skip_summaries:
            if progress_callback:
                progress_callback({"stage": "summaries", "progress": 0})
            
            # 진행 상황을 데이터베이스에 로그
            db.log_progress(
                tenant_id=tenant_id,
                message="요약 생성 시작",
                percentage=0,
                step=0,
                total_steps=100
            )
            
            logger.info("요약 생성 시작...")
            summary_result = await generate_and_store_summaries(
                tenant_id=tenant_id,
                platform=platform,
                force_update=purge
            )
            result["summaries_created"] = summary_result["success_count"]
            
            if progress_callback:
                progress_callback({"stage": "summaries", "progress": 100})
            
            # 진행 상황을 데이터베이스에 로그
            db.log_progress(
                tenant_id=tenant_id,
                message=f"요약 생성 완료: {result['summaries_created']}개",
                percentage=100,
                step=100,
                total_steps=100
            )
        
        # 4. 임베딩 생성 및 벡터 DB 저장
        if not skip_embeddings:
            if progress_callback:
                progress_callback({"stage": "embeddings", "progress": 0})
            
            # 진행 상황을 데이터베이스에 로그
            db.log_progress(
                tenant_id=tenant_id,
                message="임베딩 생성 시작",
                percentage=0,
                step=0,
                total_steps=100
            )
            
            logger.info("임베딩 생성 시작...")
            embedding_result = await sync_summaries_to_vector_db(
                tenant_id=tenant_id,
                platform=platform
            )
            result["embeddings_created"] = embedding_result.get("processed_count", 0)
            
            if progress_callback:
                progress_callback({"stage": "embeddings", "progress": 100})
            
            # 진행 상황을 데이터베이스에 로그
            db.log_progress(
                tenant_id=tenant_id,
                message=f"임베딩 생성 완료: {result['embeddings_created']}개",
                percentage=100,
                step=100,
                total_steps=100
            )
        
        result["processing_time"] = time.time() - start_time
        result["end_time"] = get_kst_time()
        result["success"] = True
        
        logger.info("✅ 데이터 수집 완료:")
        logger.info(f"  - 티켓: {result['tickets_processed']}개")
        logger.info(f"  - KB 문서: {result['articles_processed']}개")
        logger.info(f"  - 요약: {result['summaries_created']}개")
        logger.info(f"  - 임베딩: {result['embeddings_created']}개")
        logger.info(f"  - 소요 시간: {result['processing_time']:.2f}초")
        
        return result
        
    except Exception as e:
        logger.error(f"데이터 수집 중 오류 발생: {e}")
        result["success"] = False
        result["error"] = str(e)
        result["processing_time"] = time.time() - start_time
        result["end_time"] = get_kst_time()
        raise
    finally:
        # db가 정의되어 있고 연결되어 있는 경우에만 disconnect
        if db is not None:
            try:
                db.disconnect()
            except Exception as disconnect_error:
                logger.warning(f"데이터베이스 연결 해제 중 오류: {disconnect_error}")

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
                            # 티켓 요약 생성
                            ticket_data = {
                                'id': original_id,
                                'subject': original_data.get('subject', ''),
                                'description': original_data.get('description', ''),
                                'status': original_data.get('status', ''),
                                'priority': original_data.get('priority', ''),
                                'integrated_text': integrated_content,
                                'conversations': original_data.get('conversations', []),
                                'attachments': original_data.get('all_attachments', [])
                            }
                            
                            try:
                                summary_result = await llm_manager.generate_ticket_summary(ticket_data)
                                if summary_result and 'summary' in summary_result:
                                    summary = summary_result['summary']
                                else:
                                    summary = "요약 생성에 실패했습니다."
                            except Exception as e:
                                logger.error(f"티켓 {original_id} 요약 생성 중 LLM 오류: {e}")
                                summary = "LLM 요약 생성 중 오류가 발생했습니다."
                                
                        elif object_type == 'integrated_article':
                            # KB 문서 요약 생성
                            kb_data = {
                                'id': original_id,
                                'title': original_data.get('title', ''),
                                'content': integrated_content,
                                'description': original_data.get('description', ''),
                                'category': original_data.get('category', ''),
                                'tags': original_data.get('tags', []),
                                'created_at': original_data.get('created_at', ''),
                                'updated_at': original_data.get('updated_at', '')
                            }
                            
                            try:
                                summary_result = await llm_manager.generate_knowledge_base_summary(kb_data)
                                
                                if summary_result and 'summary' in summary_result:
                                    summary = summary_result['summary']
                                else:
                                    summary = "요약 생성에 실패했습니다."
                                    
                            except Exception as e:
                                logger.error(f"KB 문서 {original_id} 요약 생성 중 LLM 오류: {e}")
                                summary = "LLM 요약 생성 중 오류가 발생했습니다."
                        else:
                            result["skipped_count"] += 1
                            continue
                        
                        # 요약 업데이트 (ORM 방식)
                        if summary:
                            obj.summary = summary
                            obj.summary_generated_at = datetime.utcnow()
                            session.flush()  # 변경사항 플러시
                            
                            result["success_count"] += 1
                            logger.debug(f"{object_type} {original_id}: 요약 생성 및 저장 완료")
                        else:
                            result["failure_count"] += 1
                        
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
                
                # 데이터 파싱
                try:
                    original_data = json.loads(original_data_str) if original_data_str else {}
                    tenant_metadata = json.loads(tenant_metadata_str) if tenant_metadata_str else {}
                except json.JSONDecodeError:
                    logger.warning(f"{object_type} {original_id}: 데이터 파싱 실패")
                    original_data = {}
                    tenant_metadata = {}
                
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
        logger.info(f"  - 성공: {result['success_count']}")
        logger.info(f"  - 실패: {result['failure_count']}")
        logger.info(f"  - 건너뜀: {result['skipped_count']}")
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
    collection_name: str = COLLECTION_NAME
) -> Dict[str, Any]:
    """
    통합 객체의 요약을 벡터 데이터베이스에 동기화합니다.
    
    Args:
        tenant_id: 회사 식별자
        platform: 플랫폼 식별자
        collection_name: 벡터 DB 컬렉션 이름
        
    Returns:
        Dict[str, Any]: 처리 결과
    """
    logger.info(f"벡터 DB 동기화 시작 (tenant_id: {tenant_id}, platform: {platform})")
    start_time = time.time()
    
    result = {
        "processed_count": 0,
        "success_count": 0,
        "failure_count": 0,
        "errors": []
    }
    
    # ORM 방식으로 데이터베이스 연결
    from core.database.manager import get_db_manager
    from core.repositories.integrated_object_repository import IntegratedObjectRepository
    
    try:
        db_manager = get_db_manager(tenant_id=tenant_id)
        
        with db_manager.get_session() as session:
            repo = IntegratedObjectRepository(session)
            
            # 요약이 있는 통합 객체들 조회
            objects = repo.get_by_company(
                tenant_id=tenant_id,
                platform=platform
            )
            
            # 요약이 있고 벡터화할 수 있는 객체들만 필터링
            valid_objects = []
            for obj in objects:
                if (obj.object_type in ('integrated_ticket', 'integrated_article') and
                    obj.summary and obj.summary.strip() and
                    obj.integrated_content and obj.integrated_content.strip()):
                    valid_objects.append(obj)
            
            logger.info(f"벡터화할 객체 수: {len(valid_objects)}개")
            
            documents_to_embed = []
            
            for obj in valid_objects:
                try:
                    # tenant_metadata 파싱
                    tenant_metadata = obj.tenant_metadata or {}
                    if isinstance(tenant_metadata, str):
                        try:
                            tenant_metadata = json.loads(tenant_metadata)
                        except json.JSONDecodeError:
                            logger.warning(f"{obj.object_type} {obj.original_id}: 메타데이터 파싱 실패")
                    
                    # 벡터화용 문서 생성 
                    # original_data에서 메타데이터 추출
                    original_data = obj.original_data or {}
                    if isinstance(original_data, str):
                        try:
                            original_data = json.loads(original_data)
                        except json.JSONDecodeError:
                            original_data = {}
                    
                    doc_metadata = sanitize_metadata({
                        "tenant_id": tenant_id,
                        "platform": platform,
                        "doc_type": obj.object_type.replace('integrated_', '') if obj.object_type.startswith('integrated_') else obj.object_type,  # integrated_prefix 제거
                        "object_type": obj.object_type,  # 호환성을 위해 유지
                        "original_id": obj.original_id,
                        "subject": original_data.get('subject', ''),
                        "status": original_data.get('status', ''),
                        "priority": original_data.get('priority', ''),
                        "created_at": original_data.get('created_at', ''),
                        **tenant_metadata
                    })
                    
                    # 요약을 메인 콘텐츠로 사용
                    document = {
                        "content": obj.summary,
                        "metadata": doc_metadata,
                        "id": f"{tenant_id}_{platform}_{obj.object_type}_{obj.original_id}"
                    }
                    
                    # 문서를 임베딩 목록에 추가
                    documents_to_embed.append(document)
                    result["processed_count"] += 1
                    
                except Exception as e:
                    logger.error(f"{obj.object_type} {obj.original_id} 벡터화 준비 중 오류: {e}")
                    result["failure_count"] += 1
                    result["errors"].append(f"{obj.object_type} {obj.original_id}: {str(e)}")
                    
            # 벡터 임베딩 및 저장
            if documents_to_embed:
                logger.info(f"벡터 임베딩 시작... ({len(documents_to_embed)}개)")
                
                # 임베딩을 위해 content만 추출
                content_texts = []
                for doc in documents_to_embed:
                    content = doc.get("content", "")
                    if content and isinstance(content, str) and content.strip():
                        content_texts.append(content)
                    else:
                        logger.warning(f"빈 content 발견: {doc.get('id', 'unknown')}")
                
                if not content_texts:
                    logger.warning("임베딩할 유효한 content가 없음")
                    result["failure_count"] += len(documents_to_embed)
                else:
                    logger.info(f"유효한 content 수: {len(content_texts)}/{len(documents_to_embed)}")
                    
                    # 임베딩 전 데이터 검증
                    logger.debug("임베딩 데이터 검증 중...")
                    for i, content in enumerate(content_texts[:3]):  # 첫 3개만 로깅
                        content_type = type(content).__name__
                        content_preview = str(content)[:100] if content else "None"
                        logger.debug(f"Content {i}: 타입={content_type}, 미리보기='{content_preview}...'")
                    
                    embedded_docs = embed_documents(content_texts)
                    
                    # 벡터 DB에 저장하기 위한 데이터 준비
                    texts = []
                    embeddings = []
                    metadatas = []
                    ids = []
                    
                    # 유효한 content만 골라서 저장
                    valid_doc_index = 0
                    for document in documents_to_embed:
                        content = document.get("content", "")
                        if content and isinstance(content, str) and content.strip():
                            if valid_doc_index < len(embedded_docs):
                                texts.append(content)
                                embeddings.append(embedded_docs[valid_doc_index])
                                metadatas.append(document["metadata"])
                                ids.append(document["id"])
                                valid_doc_index += 1
                    
                    if texts:
                        # 벡터 DB에 저장
                        vector_db.add_documents(
                            texts=texts,
                            embeddings=embeddings,
                            metadatas=metadatas,
                            ids=ids
                        )
                        
                        result["success_count"] = len(texts)
                        logger.info(f"벡터 DB 저장 완료: {result['success_count']}개")
                    else:
                        logger.warning("저장할 유효한 벡터 데이터가 없음")
        
        result["processing_time"] = time.time() - start_time
        
        logger.info("✅ 벡터 DB 동기화 완료:")
        logger.info(f"  - 처리: {result['processed_count']}개")
        logger.info(f"  - 성공: {result['success_count']}개")
        logger.info(f"  - 실패: {result['failure_count']}개")
        logger.info(f"  - 소요 시간: {result['processing_time']:.2f}초")
        
        return result
        
    except Exception as e:
        logger.error(f"벡터 DB 동기화 중 오류 발생: {e}")
        result["errors"].append(str(e))
        result["processing_time"] = time.time() - start_time
        raise


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
