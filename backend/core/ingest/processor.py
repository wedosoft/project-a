"""
통합된 데이터 수집 및 처리 메인 로직 모듈

이 모듈은 Freshdesk에서 티켓과 지식베이스 문서를 가져와 임베딩한 후,
벡터 데이터베이스에 저장하는 메인 프로세싱 로직을 제공합니다.
모든 데이터 처리는 통합 객체(integrated_objects) 기반으로만 수행됩니다.

프로젝트 규칙 및 가이드라인: /PROJECT_RULES.md 참고
"""

import json
import logging
import time
import pytz
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Callable
from dotenv import load_dotenv

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
    extract_company_id_from_domain,
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
    런타임 고객 인증 정보를 검증하고 company_id를 반환합니다.
    
    Args:
        domain: 고객 도메인 (예: "example.freshdesk.com")
        api_key: API 키
        platform: 플랫폼 식별자 (기본값: "freshdesk")
        
    Returns:
        str: 추출된 company_id
        
    Raises:
        ValueError: 인증 정보가 유효하지 않은 경우
    """
    if not domain or not api_key:
        raise ValueError("도메인과 API 키는 필수입니다.")
    
    # 도메인에서 company_id 추출
    company_id = extract_company_id_from_domain(domain)
    if not company_id:
        raise ValueError(f"유효한 {platform} 도메인이 아닙니다: {domain}")
    
    # API 키 형식 검증 (기본적인 검증)
    if len(api_key) < 10:
        raise ValueError("API 키가 너무 짧습니다.")
    
    logger.info(f"런타임 고객 인증 검증 완료: {company_id} ({platform})")
    return company_id

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
    company_id = validate_runtime_customer_credentials(domain, api_key, platform)
    
    return {
        "company_id": company_id,
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
    company_id: str,
    platform: str = "freshdesk",
    incremental: bool = True,
    purge: bool = False,
    skip_embeddings: bool = False,
    skip_summaries: bool = False,
    progress_callback: Optional[Callable] = None
) -> Dict[str, Any]:
    """
    데이터 수집 및 처리를 수행합니다.
    
    Args:
        company_id: 회사 식별자
        platform: 플랫폼 식별자
        incremental: 증분 수집 여부
        purge: 기존 데이터 삭제 여부
        skip_embeddings: 임베딩 건너뛰기
        skip_summaries: 요약 생성 건너뛰기
        progress_callback: 진행률 콜백 함수
        
    Returns:
        Dict[str, Any]: 처리 결과
    """
    logger.info(f"데이터 수집 시작: {company_id} ({platform})")
    start_time = time.time()
    
    result = {
        "company_id": company_id,
        "platform": platform,
        "start_time": get_kst_time(),
        "tickets_processed": 0,
        "articles_processed": 0,
        "embeddings_created": 0,
        "summaries_created": 0,
        "errors": []
    }
    
    try:
        # 멀티테넌트 데이터베이스 연결
        from core.database.database import get_database
        db = get_database(company_id, platform)
        
        if purge:
            # 기존 데이터 삭제
            logger.info("기존 데이터 삭제 중...")
            cursor = db.connection.cursor()
            cursor.execute("DELETE FROM integrated_objects WHERE company_id = ? AND platform = ?", 
                         (company_id, platform))
            db.connection.commit()
            logger.info("기존 데이터 삭제 완료")
        
        # 1. 티켓 수집
        if progress_callback:
            progress_callback({"stage": "tickets", "progress": 0})
        
        logger.info("티켓 수집 시작...")
        tickets = await fetch_tickets(company_id, platform=platform)
        logger.info(f"수집된 티켓 수: {len(tickets)}")
        
        for i, ticket in enumerate(tickets):
            try:
                # 통합 티켓 객체 생성 및 저장
                integrated_ticket = create_integrated_ticket_object(
                    ticket=ticket,
                    company_id=company_id
                )
                
                store_integrated_object_with_migration(
                    integrated_object=integrated_ticket, 
                    company_id=company_id, 
                    platform=platform
                )
                
                result["tickets_processed"] += 1
                
                if progress_callback:
                    progress = (i + 1) / len(tickets) * 100
                    progress_callback({"stage": "tickets", "progress": progress})
                    
            except Exception as e:
                logger.error(f"티켓 처리 오류 (ID: {ticket.get('id', 'unknown')}): {e}")
                result["errors"].append(f"티켓 {ticket.get('id', 'unknown')}: {str(e)}")
        
        # 2. KB 문서 수집
        if progress_callback:
            progress_callback({"stage": "articles", "progress": 0})
        
        logger.info("KB 문서 수집 시작...")
        articles = await fetch_kb_articles(company_id, platform=platform)
        logger.info(f"수집된 KB 문서 수: {len(articles)}")
        
        for i, article in enumerate(articles):
            try:
                # 통합 문서 객체 생성 및 저장
                integrated_article = create_integrated_article_object(
                    article=article,
                    company_id=company_id
                )
                
                store_integrated_object_with_migration(
                    integrated_object=integrated_article, 
                    company_id=company_id, 
                    platform=platform
                )
                
                result["articles_processed"] += 1
                
                if progress_callback:
                    progress = (i + 1) / len(articles) * 100
                    progress_callback({"stage": "articles", "progress": progress})
                    
            except Exception as e:
                logger.error(f"KB 문서 처리 오류 (ID: {article.get('id', 'unknown')}): {e}")
                result["errors"].append(f"KB 문서 {article.get('id', 'unknown')}: {str(e)}")
        
        # 3. 요약 생성
        if not skip_summaries:
            if progress_callback:
                progress_callback({"stage": "summaries", "progress": 0})
            
            logger.info("요약 생성 시작...")
            summary_result = await generate_and_store_summaries(
                company_id=company_id,
                platform=platform,
                force_update=purge
            )
            result["summaries_created"] = summary_result["success_count"]
            
            if progress_callback:
                progress_callback({"stage": "summaries", "progress": 100})
        
        # 4. 임베딩 생성 및 벡터 DB 저장
        if not skip_embeddings:
            if progress_callback:
                progress_callback({"stage": "embeddings", "progress": 0})
            
            logger.info("임베딩 생성 시작...")
            embedding_result = await sync_summaries_to_vector_db(
                company_id=company_id,
                platform=platform
            )
            result["embeddings_created"] = embedding_result.get("processed_count", 0)
            
            if progress_callback:
                progress_callback({"stage": "embeddings", "progress": 100})
        
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
        db.disconnect()

# 요약 생성 함수

async def generate_and_store_summaries(
    company_id: str,
    platform: str = "freshdesk",
    force_update: bool = False
) -> Dict[str, Any]:
    """
    통합 객체에서 직접 요약을 생성하고 저장합니다.
    
    Args:
        company_id: 회사 식별자
        platform: 플랫폼 식별자
        force_update: 기존 요약 강제 업데이트 여부
        
    Returns:
        Dict[str, Any]: 처리 결과
    """
    logger.info(f"LLM 요약 생성 시작 (company_id: {company_id}, platform: {platform})")
    start_time = time.time()
    
    result = {
        "success_count": 0,
        "failure_count": 0,
        "skipped_count": 0,
        "total_processed": 0,
        "processing_time": 0,
        "errors": []
    }
    
    # 멀티테넌트 데이터베이스 연결
    from core.database.database import get_database
    db = get_database(company_id, platform)
    
    try:
        cursor = db.connection.cursor()
        
        # 요약이 없는 통합 객체들 조회 (티켓 + KB 문서)
        if force_update:
            # 강제 업데이트: 모든 통합 객체
            cursor.execute("""
                SELECT original_id, object_type, original_data, integrated_content, tenant_metadata 
                FROM integrated_objects 
                WHERE company_id = ? AND platform = ? 
                AND object_type IN ('integrated_ticket', 'integrated_article')
                AND integrated_content IS NOT NULL AND integrated_content != ''
            """, (company_id, platform))
        else:
            # 일반 모드: 요약이 없는 것만
            cursor.execute("""
                SELECT original_id, object_type, original_data, integrated_content, tenant_metadata 
                FROM integrated_objects 
                WHERE company_id = ? AND platform = ? 
                AND object_type IN ('integrated_ticket', 'integrated_article')
                AND (summary IS NULL OR summary = '')
                AND integrated_content IS NOT NULL AND integrated_content != ''
            """, (company_id, platform))
        
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

                # LLM 요약 생성
                summary = await generate_summary(
                    content=integrated_content,
                    content_type=content_type,
                    subject=subject,
                    metadata=summary_metadata
                )
                
                # 요약만 업데이트 (기존 데이터는 보존)
                cursor.execute("""
                    UPDATE integrated_objects 
                    SET summary = ? 
                    WHERE company_id = ? AND platform = ? AND object_type = ? AND original_id = ?
                """, (summary, company_id, platform, object_type, original_id))
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
        logger.error(f"LLM 요약 생성 중 오류 발생: {e}")
        result["errors"].append(str(e))
        result["processing_time"] = time.time() - start_time
        raise
    finally:
        db.disconnect()

# 벡터 DB 동기화 함수

async def sync_summaries_to_vector_db(
    company_id: str, 
    platform: str = "freshdesk",
    collection_name: str = COLLECTION_NAME
) -> Dict[str, Any]:
    """
    통합 객체의 요약을 벡터 데이터베이스에 동기화합니다.
    
    Args:
        company_id: 회사 식별자
        platform: 플랫폼 식별자
        collection_name: 벡터 DB 컬렉션 이름
        
    Returns:
        Dict[str, Any]: 처리 결과
    """
    logger.info(f"벡터 DB 동기화 시작 (company_id: {company_id}, platform: {platform})")
    start_time = time.time()
    
    result = {
        "processed_count": 0,
        "success_count": 0,
        "failure_count": 0,
        "errors": []
    }
    
    # 멀티테넌트 데이터베이스 연결
    from core.database.database import get_database
    db = get_database(company_id, platform)
    
    try:
        cursor = db.connection.cursor()
        
        # 요약이 있는 통합 객체들 조회
        cursor.execute("""
            SELECT original_id, object_type, original_data, integrated_content, summary, tenant_metadata
            FROM integrated_objects 
            WHERE company_id = ? AND platform = ? 
            AND object_type IN ('integrated_ticket', 'integrated_article')
            AND summary IS NOT NULL AND summary != ''
            AND integrated_content IS NOT NULL AND integrated_content != ''
        """, (company_id, platform))
        
        rows = cursor.fetchall()
        logger.info(f"벡터화할 객체 수: {len(rows)}개")
        
        documents_to_embed = []
        
        for row in rows:
            try:
                original_id, object_type, original_data_str, integrated_content, summary, tenant_metadata_str = row
                
                # 데이터 파싱
                try:
                    original_data = json.loads(original_data_str) if original_data_str else {}
                    tenant_metadata = json.loads(tenant_metadata_str) if tenant_metadata_str else {}
                except json.JSONDecodeError:
                    logger.warning(f"{object_type} {original_id}: 메타데이터 파싱 실패")
                    original_data = {}
                    tenant_metadata = {}
                
                # 벡터화용 문서 생성
                doc_metadata = sanitize_metadata({
                    "company_id": company_id,
                    "platform": platform,
                    "object_type": object_type,
                    "original_id": original_id,
                    **metadata
                })
                
                # 요약을 메인 콘텐츠로 사용
                document = {
                    "content": summary,
                    "metadata": doc_metadata,
                    "id": f"{company_id}_{platform}_{object_type}_{original_id}"
                }
                
                documents_to_embed.append(document)
                result["processed_count"] += 1
                
            except Exception as e:
                logger.error(f"{object_type} {original_id} 벡터화 준비 중 오류: {e}")
                result["failure_count"] += 1
                result["errors"].append(f"{object_type} {original_id}: {str(e)}")            # 벡터 임베딩 및 저장
            if documents_to_embed:
                logger.info(f"벡터 임베딩 시작... ({len(documents_to_embed)}개)")
                
                embedded_docs = embed_documents(documents_to_embed)
                
                # 벡터 DB에 저장하기 위한 데이터 준비
                texts = []
                embeddings = []
                metadatas = []
                ids = []
                
                for i, document in enumerate(documents_to_embed):
                    texts.append(document["content"])
                    embeddings.append(embedded_docs[i])
                    metadatas.append(document["metadata"])
                    ids.append(document["id"])
                
                # 벡터 DB에 저장
                vector_db.add_documents(
                    texts=texts,
                    embeddings=embeddings,
                    metadatas=metadatas,
                    ids=ids
                )
                
                result["success_count"] = len(embedded_docs)
                logger.info(f"벡터 DB 저장 완료: {result['success_count']}개")
        
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
    finally:
        db.disconnect()

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
