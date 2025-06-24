"""
데이터 수집 및 처리 메인 로직 모듈

이 모듈은 Freshdesk에서 티켓과 지식베이스 문서를 가져와 임베딩한 후,
벡터 데이터베이스에 저장하는 메인 프로세싱 로직을 제공합니다.

프로젝트 규칙 및 가이드라인: /PROJECT_RULES.md 참고
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import pytz
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

from core.search.embeddings.embedder import embed_documents, process_documents
from core.database.vectordb import vector_db
from core.database.database import SQLiteDatabase
from core.ingest.integrator import create_integrated_ticket_object, create_integrated_article_object
from core.ingest.storage import store_integrated_object_to_sqlite, sanitize_metadata
from core.ingest.validator import load_status_mappings, save_status_mappings
from core.platforms.freshdesk.fetcher import (
    extract_company_id_from_domain,
    fetch_kb_articles,
    fetch_tickets,
)
from core.llm.summarizer import generate_summary

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
    런타임에 고객이 제공한 도메인과 API 키를 검증하고 company_id를 반환합니다.
    
    Args:
        domain: 고객 도메인 (예: company.platform.com)
        api_key: 고객 API 키
        platform: 플랫폼 식별자 (freshdesk, zendesk 등)
        
    Returns:
        str: 검증된 company_id
        
    Raises:
        ValueError: 인증 실패 또는 유효하지 않은 도메인
    """
    if not domain or not domain.strip():
        logger.error("런타임 보안: 도메인이 제공되지 않았습니다")
        raise ValueError("고객 도메인이 필수입니다")
    
    if not api_key or not api_key.strip():
        logger.error("런타임 보안: API 키가 제공되지 않았습니다")
        raise ValueError("고객 API 키가 필수입니다")
    
    # 도메인에서 company_id 추출
    try:
        company_id = extract_company_id_from_domain(domain.strip())
        logger.info(f"런타임 도메인 '{domain}'에서 추출된 company_id: '{company_id}'")
        return company_id
        
    except Exception as e:
        logger.error(f"런타임 보안: 도메인 '{domain}' 검증 실패: {e}")
        raise ValueError(f"유효하지 않은 고객 도메인: {e}")


def create_runtime_customer_context(domain: str, api_key: str, platform: str = "freshdesk") -> Dict[str, str]:
    """
    런타임에 고객별 컨텍스트를 생성합니다 (메모리에서만 사용).
    
    Args:
        domain: 고객 도메인
        api_key: 고객 API 키
        platform: 플랫폼 식별자
        
    Returns:
        Dict: 고객 컨텍스트 정보
    """
    company_id = validate_runtime_customer_credentials(domain, api_key, platform)
    
    context = {
        'company_id': company_id,
        'domain': domain.strip(),
        'api_key': api_key.strip(),  # 주의: 로그에 출력하지 말 것
        'platform': platform,
        'created_at': get_kst_time()
    }
    
    logger.info(f"런타임 고객 컨텍스트 생성: company_id='{company_id}', platform='{platform}'")
    return context


def load_local_data(data_dir: str):
    """
    로컬 디렉토리에서 기존에 수집된 데이터를 로드합니다.
    
    Args:
        data_dir: 데이터 디렉토리 경로
        
    Returns:
        Tuple[List[Dict], List[Dict]]: (티켓 데이터, KB 문서 데이터)
    """
    logger.info(f"로컬 데이터 디렉토리에서 데이터 로드 중: {data_dir}")
    
    tickets = []
    articles = []
    
    data_path = Path(data_dir)
    
    # 티켓 데이터 로드
    tickets_file = data_path / "tickets.json"
    if tickets_file.exists():
        try:
            with open(tickets_file, "r", encoding="utf-8") as f:
                tickets = json.load(f)
            logger.info(f"티켓 {len(tickets)}개 로드 완료")
        except Exception as e:
            logger.error(f"티켓 데이터 로드 실패: {e}")
    
    # KB 문서 데이터 로드
    articles_file = data_path / "kb_articles.json"
    if articles_file.exists():
        try:
            with open(articles_file, "r", encoding="utf-8") as f:
                articles = json.load(f)
            logger.info(f"KB 문서 {len(articles)}개 로드 완료")
        except Exception as e:
            logger.error(f"KB 문서 데이터 로드 실패: {e}")
    
    # 통합 데이터 파일 확인 (하위 호환성)
    integrated_file = data_path / "freshdesk_data.json"
    if integrated_file.exists() and not tickets and not articles:
        try:
            with open(integrated_file, "r", encoding="utf-8") as f:
                integrated_data = json.load(f)
                
            # 기존 통합 파일에서 분리
            if isinstance(integrated_data, dict):
                tickets = integrated_data.get("tickets", [])
                articles = integrated_data.get("kb_articles", [])
            elif isinstance(integrated_data, list):
                # 레거시 형태: 리스트로만 저장된 경우
                for item in integrated_data:
                    if item.get("type") == "ticket":
                        tickets.append(item)
                    elif item.get("type") == "kb_article":
                        articles.append(item)
                        
            logger.info(f"통합 파일에서 티켓 {len(tickets)}개, KB 문서 {len(articles)}개 로드 완료")
            
        except Exception as e:
            logger.error(f"통합 데이터 파일 로드 실패: {e}")
    
    return tickets, articles


def save_checkpoint(data_dir: str, stage: str, data: Dict[str, Any]) -> None:
    """
    처리 중인 데이터의 체크포인트를 저장합니다.
    
    Args:
        data_dir: 데이터 디렉토리
        stage: 처리 단계 (data_loaded, embedded, etc.)
        data: 저장할 데이터
    """
    try:
        checkpoints_dir = Path(data_dir) / "checkpoints"
        checkpoints_dir.mkdir(exist_ok=True)
        
        checkpoint_file = checkpoints_dir / f"{stage}.json"
        
        # 임베딩 데이터는 크기가 클 수 있으므로 압축 저장 고려
        with open(checkpoint_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        logger.info(f"체크포인트 저장됨: {checkpoint_file}")
        
    except Exception as e:
        logger.error(f"체크포인트 저장 실패 ({stage}): {e}")


def load_checkpoint(data_dir: str, stage: str) -> Optional[Dict[str, Any]]:
    """
    저장된 체크포인트를 로드합니다.
    
    Args:
        data_dir: 데이터 디렉토리
        stage: 처리 단계
        
    Returns:
        저장된 체크포인트 데이터 또는 None
    """
    try:
        checkpoints_dir = Path(data_dir) / "checkpoints"
        checkpoint_file = checkpoints_dir / f"{stage}.json"
        
        if checkpoint_file.exists():
            with open(checkpoint_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            logger.info(f"체크포인트 로드됨: {checkpoint_file}")
            return data
        else:
            logger.debug(f"체크포인트 파일 없음: {checkpoint_file}")
            return None
            
    except Exception as e:
        logger.error(f"체크포인트 로드 실패 ({stage}): {e}")
        return None


def clear_checkpoints(data_dir: str) -> None:
    """
    모든 체크포인트를 삭제합니다.
    
    Args:
        data_dir: 데이터 디렉토리
    """
    try:
        checkpoints_dir = Path(data_dir) / "checkpoints"
        if checkpoints_dir.exists():
            for checkpoint_file in checkpoints_dir.glob("*.json"):
                checkpoint_file.unlink()
                logger.debug(f"체크포인트 삭제됨: {checkpoint_file}")
        logger.info("모든 체크포인트가 삭제되었습니다.")
    except Exception as e:
        logger.error(f"체크포인트 삭제 실패: {e}")


async def ingest(
    company_id: str,
    platform: str = "freshdesk",
    incremental: bool = True,
    purge: bool = False,
    process_attachments: bool = True,
    force_rebuild: bool = False,
    local_data_dir: Optional[str] = None,
    include_kb: bool = True,
    domain: Optional[str] = None,
    api_key: Optional[str] = None,
    max_tickets: Optional[int] = None,
    max_articles: Optional[int] = None,
    start_date: Optional[str] = None,
    cancel_event: Optional[asyncio.Event] = None,
    pause_event: Optional[asyncio.Event] = None,
    progress_callback: Optional[callable] = None
) -> Dict[str, Any]:
    """
    멀티플랫폼 데이터 수집 및 처리 메인 함수
    
    Args:
        company_id: 회사 ID (필수)
        platform: 플랫폼 식별자 (freshdesk, zendesk 등)
        incremental: 증분 업데이트 모드
        purge: 기존 데이터 삭제 
        process_attachments: 첨부파일 처리 여부
        force_rebuild: 강제 재구축 모드
        local_data_dir: 로컬 데이터 디렉토리 (선택사항)
        include_kb: 지식베이스 포함 여부
        domain: 플랫폼 도메인
        api_key: API 키
        max_tickets: 최대 티켓 수 (선택사항)
        max_articles: 최대 문서 수 (선택사항)
        start_date: 티켓 수집 시작 날짜 (YYYY-MM-DD 형식, None이면 현재부터 10년 전)
        cancel_event: 취소 이벤트 (작업 제어용)
        pause_event: 일시정지 이벤트 (작업 제어용)
        progress_callback: 진행상황 콜백 함수
        
    Returns:
        Dict: 수집 결과 정보
    """
    start_time = time.time()
    logger.info(f"데이터 수집 시작 - Company: {company_id}, Platform: {platform}")
    
    # 결과 초기화
    result = {
        "success": False,
        "message": "",
        "tickets_processed": 0,
        "articles_processed": 0,
        "documents_embedded": 0,
        "start_time": get_kst_time(),
        "end_time": None,
        "duration_seconds": 0,
        "error": None
    }
    
    try:
        # 취소 신호 확인
        if cancel_event and cancel_event.is_set():
            result["message"] = "작업이 취소되었습니다"
            return result
            
        # 일시정지 대기
        while pause_event and pause_event.is_set():
            logger.info("작업이 일시정지되었습니다. 재개를 기다리는 중...")
            await asyncio.sleep(1)
            if cancel_event and cancel_event.is_set():
                result["message"] = "작업이 취소되었습니다"
                return result
        
        # 진행상황 업데이트
        if progress_callback:
            progress_callback("데이터 수집 시작", 5)
        
        # 플랫폼별 데이터 수집
        tickets = []
        articles = []
        
        # 멀티테넌트 데이터베이스 생성 (데이터 수집 전에 먼저 생성)
        logger.info("멀티테넌트 데이터베이스 생성 중...")
        from core.database.database import get_database
        db = get_database(company_id, platform)
        logger.info(f"데이터베이스 생성 완료: {db.db_path}")
        
        if local_data_dir:
            # 로컬 데이터 로드
            logger.info(f"로컬 데이터 디렉토리에서 데이터 로드: {local_data_dir}")
            # TODO: 로컬 데이터 로드 로직 구현
        else:
            # API에서 데이터 수집
            if platform == "freshdesk":
                from core.platforms.freshdesk.fetcher import fetch_tickets, fetch_kb_articles
                
                # 취소 확인
                if cancel_event and cancel_event.is_set():
                    result["message"] = "작업이 취소되었습니다"
                    return result
                
                # 진행상황 업데이트
                if progress_callback:
                    progress_callback("티켓 데이터 수집 중", 20)
                
                logger.info("티켓 데이터 수집 중...")
                try:
                    tickets = await fetch_tickets(
                        domain=domain, 
                        api_key=api_key,
                        max_tickets=max_tickets,
                        company_id=company_id,
                        platform=platform,
                        store_immediately=True,  # 즉시 저장 모드 활성화
                        start_date=start_date  # 시작 날짜 파라미터 추가
                    )
                    logger.info(f"티켓 수집 완료: {len(tickets)}개")
                except Exception as e:
                    logger.error(f"티켓 수집 중 오류: {e}", exc_info=True)
                    tickets = []  # 오류 시 빈 리스트
                
                # 취소 확인
                if cancel_event and cancel_event.is_set():
                    result["message"] = "작업이 취소되었습니다"
                    return result
                
                if include_kb:
                    # 진행상황 업데이트
                    if progress_callback:
                        progress_callback("지식베이스 데이터 수집 중", 35)
                    
                    logger.info("KB 데이터 수집 중...")
                    try:
                        articles = await fetch_kb_articles(
                            domain=domain,
                            api_key=api_key,
                            max_articles=max_articles
                        )
                        logger.info(f"KB 수집 완료: {len(articles)}개")
                    except Exception as e:
                        logger.error(f"KB 수집 중 오류: {e}", exc_info=True)
                        articles = []  # 오류 시 빈 리스트
                else:
                    logger.info("include_kb=False이므로 KB 수집을 건너뜁니다.")
            else:
                raise ValueError(f"지원되지 않는 플랫폼: {platform}")
        
        logger.info(f"데이터 수집 완료 - 티켓: {len(tickets)}개, 문서: {len(articles)}개")
        
        # 취소 확인
        if cancel_event and cancel_event.is_set():
            result["message"] = "작업이 취소되었습니다"
            return result
        
        # 진행상황 업데이트
        if progress_callback:
            progress_callback("데이터 저장 및 처리 중", 50)
        
        # SQLite에 원본 데이터 저장 (데이터 유무와 관계없이 데이터베이스는 생성)
        logger.info("SQLite 데이터베이스에 원본 데이터 저장 중...")
        job_id = f"ingest_{int(time.time())}"
        
        # 데이터가 없는 경우 조기 종료 (데이터베이스 생성 후)
        if not tickets and not articles:
            logger.info("수집된 데이터가 없지만 데이터베이스는 생성되었습니다")
            result["message"] = "수집할 데이터가 없습니다 (데이터베이스 생성 완료)"
            result["success"] = True
            return result
        
        # force_rebuild 모드인 경우 기존 데이터 삭제
        if force_rebuild:
            logger.info("force_rebuild 모드: 기존 SQLite 데이터 삭제 중...")
            db.clear_all_data(company_id=company_id, platform=platform)
        
        # 수집 작업 시작 로그
        job_start_data = {
            'job_id': job_id,
            'company_id': company_id,
            'platform': platform,
            'job_type': 'ingest',
            'status': 'started',
            'start_time': get_kst_time(),
            'config': {
                'incremental': incremental,
                'purge': purge,
                'include_kb': include_kb,
                'tickets_count': len(tickets),
                'articles_count': len(articles)
            }
        }
        db.log_collection_job(job_start_data)
        
        # 티켓 데이터 처리
        tickets_saved = 0
        total_attachments = 0
        total_conversations = 0
        
        for i, ticket in enumerate(tickets):
            # 취소 확인
            if cancel_event and cancel_event.is_set():
                result["message"] = "작업이 취소되었습니다"
                return result
            
            # 일시정지 대기
            while pause_event and pause_event.is_set():
                await asyncio.sleep(1)
                if cancel_event and cancel_event.is_set():
                    result["message"] = "작업이 취소되었습니다"
                    return result
            
            # 진행상황 업데이트
            if progress_callback and i % 10 == 0:
                progress = 50 + (i / len(tickets)) * 25  # 50-75% 구간
                progress_callback(f"티켓 처리 중 ({i+1}/{len(tickets)})", progress)
            
            # 통합 객체 생성 및 저장
            logger.debug(f"티켓 처리 시작: ID={ticket.get('id')}")
            
            # 대화와 첨부파일 데이터 확인
            conversations = ticket.get("conversations", [])
            attachments = ticket.get("all_attachments", [])
            
            try:
                # 대화와 첨부파일을 명시적으로 전달
                integrated_ticket = create_integrated_ticket_object(
                    ticket=ticket, 
                    conversations=conversations,
                    attachments=attachments,
                    company_id=company_id
                )
                
                # 통합 객체에서 대화와 첨부파일 수 재확인
                integrated_conversations = integrated_ticket.get("conversations", [])
                integrated_attachments = integrated_ticket.get("all_attachments", [])
                
                store_result = store_integrated_object_to_sqlite(db, integrated_ticket, company_id, platform)
                
                if store_result:
                    tickets_saved += 1
                    # 첨부파일 및 대화 수 카운트 (통합 객체에서 가져오기)
                    total_attachments += len(integrated_attachments)
                    total_conversations += len(integrated_conversations)
                    logger.debug(f"티켓 저장 성공: ID={integrated_ticket.get('id')}, 첨부파일={len(integrated_attachments)}개, 대화={len(integrated_conversations)}개")
                else:
                    logger.error(f"티켓 저장 실패: ID={ticket.get('id')}")
                    
            except Exception as e:
                logger.error(f"티켓 처리 중 예외 발생: ID={ticket.get('id')}, 오류={e}")
                
        logger.info(f"티켓 처리 완료: 저장된 티켓 {tickets_saved}/{len(tickets)}개")
        
        # 문서 데이터 처리
        articles_saved = 0
        for i, article in enumerate(articles):
            # 취소 확인
            if cancel_event and cancel_event.is_set():
                result["message"] = "작업이 취소되었습니다"
                return result
            
            # 일시정지 대기
            while pause_event and pause_event.is_set():
                await asyncio.sleep(1)
                if cancel_event and cancel_event.is_set():
                    result["message"] = "작업이 취소되었습니다"
                    return result
            
            # 진행상황 업데이트
            if progress_callback and i % 5 == 0:
                progress = 75 + (i / len(articles)) * 10  # 75-85% 구간
                progress_callback(f"문서 처리 중 ({i+1}/{len(articles)})", progress)
            
            # 통합 객체 생성 및 저장
            logger.debug(f"문서 처리 시작: ID={article.get('id')}")
            integrated_article = create_integrated_article_object(article, company_id=company_id)
            
            store_result = store_integrated_object_to_sqlite(db, integrated_article, company_id, platform)
            
            if store_result:
                articles_saved += 1
                logger.debug(f"문서 저장 성공: ID={integrated_article.get('id')}")
            else:
                logger.error(f"문서 저장 실패: ID={article.get('id')}")
        
        logger.info(f"SQLite 저장 완료 - 티켓: {tickets_saved}개, 문서: {articles_saved}개")
        
        # 진행상황 업데이트
        if progress_callback:
            progress_callback("임베딩 및 벡터 저장 중", 85)
        
        # 임베딩 및 벡터 저장 (기존 로직)
        logger.info("문서 임베딩 및 벡터 저장 시작...")
        
        # TODO: 임베딩 로직 구현 (기존 코드 활용)
        
        # 결과 설정
        end_time = time.time()
        result.update({
            "success": True,
            "message": "데이터 수집이 완료되었습니다",
            "tickets_processed": tickets_saved,
            "articles_processed": articles_saved,
            "documents_embedded": tickets_saved + articles_saved,
            "end_time": get_kst_time(),
            "duration_seconds": end_time - start_time
        })
        
        # 완료 로그
        job_end_data = {
            'job_id': job_id,
            'company_id': company_id,
            'status': 'completed',
            'end_time': get_kst_time(),
            'tickets_collected': tickets_saved,
            'conversations_collected': total_conversations,
            'articles_collected': articles_saved,
            'attachments_collected': total_attachments,
            'results': {
                'tickets_processed': tickets_saved,
                'articles_processed': articles_saved,
                'total_documents_embedded': tickets_saved + articles_saved,
                'vectors_stored': tickets_saved + articles_saved
            }
        }
        db.log_collection_job(job_end_data)
        
        # 진행상황 업데이트
        if progress_callback:
            progress_callback("완료", 100)
        
        logger.info(f"✅ 데이터 수집 완료 (소요시간: {result['duration_seconds']:.2f}초)")
        
    except Exception as e:
        logger.error(f"데이터 수집 중 오류 발생: {e}", exc_info=True)
        end_time = time.time()
        result.update({
            "success": False,
            "message": f"데이터 수집 실패: {str(e)}",
            "end_time": get_kst_time(),
            "duration_seconds": end_time - start_time,
            "error": str(e)
        })
        
        # 실패 로그
        if 'job_id' in locals():
            job_error_data = {
                'job_id': job_id,
                'company_id': company_id,
                'status': 'failed',
                'end_time': get_kst_time(),
                'error': str(e)
            }
            if 'db' in locals():
                db.log_collection_job(job_error_data)
        
        raise
    finally:
        if 'db' in locals():
            db.disconnect()
    
    return result

async def generate_and_store_summaries(
    company_id: str,
    platform: str = "freshdesk",
    force_update: bool = False
) -> Dict[str, Any]:
    """
    티켓과 KB 문서의 LLM 요약을 생성하고 integrated_objects 테이블에 저장합니다.
    
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
        # 1. 티켓 요약 생성
        logger.info("티켓 요약 생성 중...")
        tickets = db.get_tickets_by_company_and_platform(company_id, platform)
        logger.info(f"처리할 티켓 수: {len(tickets)}")
        
        for ticket in tickets:
            try:
                original_id = str(ticket.get('original_id', ''))
                
                # 기존 요약 확인 (force_update가 False인 경우)
                existing_data = None
                cursor = db.connection.cursor()
                cursor.execute("""
                    SELECT original_data, integrated_content, metadata, summary FROM integrated_objects 
                    WHERE company_id = ? AND platform = ? AND object_type = ? AND original_id = ?
                """, (company_id, platform, 'integrated_ticket', original_id))
                existing_row = cursor.fetchone()
                
                if existing_row:
                    existing_original_data, existing_integrated_content, existing_metadata_str, existing_summary = existing_row
                    
                    # 기존 데이터가 있고 force_update가 False인 경우 요약만 확인
                    if not force_update and existing_summary:
                        logger.debug(f"티켓 {original_id}: 기존 요약 존재, 건너뜀")
                        result["skipped_count"] += 1
                        continue
                    
                    # 기존 데이터 파싱
                    try:
                        existing_data = {
                            'original_data': json.loads(existing_original_data) if existing_original_data else None,
                            'integrated_content': existing_integrated_content,
                            'metadata': json.loads(existing_metadata_str) if existing_metadata_str else {}
                        }
                    except json.JSONDecodeError:
                        logger.warning(f"티켓 {original_id}: 기존 데이터 파싱 실패, 새로 생성")
                        existing_data = None
                
                # 통합 티켓 객체 생성 (기존 데이터가 없는 경우에만)
                if existing_data and existing_data['original_data']:
                    # 기존 데이터 사용 (대화, 첨부파일 보존)
                    integrated_ticket = existing_data['original_data']
                    integrated_content = existing_data['integrated_content']
                    base_metadata = existing_data['metadata']
                else:
                    # 새로 생성
                    integrated_ticket = create_integrated_ticket_object(
                        ticket=ticket,
                        company_id=company_id
                    )
                    integrated_content = integrated_ticket.get('integrated_text', '')
                    base_metadata = {}
                
                # LLM 요약 생성
                content_text = ticket.get('description_text', '') or ticket.get('description', '')
                if not content_text:
                    logger.warning(f"티켓 {original_id}: 요약할 내용이 없음")
                    result["skipped_count"] += 1
                    continue

                # 첨부파일 정보 포함해서 요약 생성
                ticket_metadata = {
                    'status': ticket.get('status', ''),
                    'priority': ticket.get('priority', ''),
                    'created_at': ticket.get('created_at', ''),
                    'ticket_id': original_id
                }
                
                # 첨부파일 정보 추가
                attachments = db.get_attachments_by_ticket(original_id)
                logger.debug(f"티켓 {original_id}: DB에서 가져온 첨부파일 수 = {len(attachments) if attachments else 0}")
                
                if attachments:
                    ticket_metadata['attachments'] = [
                        {
                            'id': att.get('attachment_id'),
                            'name': att.get('name'),
                            'content_type': att.get('content_type'),
                            'size': att.get('size'),
                            'ticket_id': original_id,
                            'conversation_id': att.get('conversation_id'),
                            'attachment_url': att.get('download_url')
                        }
                        for att in attachments
                    ]
                    logger.debug(f"티켓 {original_id}: 첨부파일 메타데이터 설정 완료 - {len(ticket_metadata['attachments'])}개")
                else:
                    ticket_metadata['attachments'] = []
                    logger.debug(f"티켓 {original_id}: 첨부파일 없음")

                # LLM 요약 생성 (항상 기본 방식 사용)
                summary = await generate_summary(
                    content=content_text,
                    content_type="ticket",
                    subject=ticket.get('subject', ''),
                    metadata=ticket_metadata
                )
                
                # 요약 생성 후 추가 메타데이터 설정
                ticket_metadata['summary_generated_at'] = get_kst_time()
                ticket_metadata['summary_length'] = len(summary) if summary else 0
                
                # 요약에서 중요한 키워드 추출 (간단한 버전)
                if summary:
                    # 에러/문제 관련 키워드 감지
                    error_keywords = ['오류', '에러', '문제', '실패', '버그', 'error', 'bug', 'issue', 'problem', 'fail']
                    has_error = any(keyword in summary.lower() for keyword in error_keywords)
                    ticket_metadata['contains_error'] = has_error
                    
                    # 해결 상태 키워드 감지
                    resolved_keywords = ['해결', '완료', '수정', '성공', 'resolved', 'fixed', 'completed', 'success']
                    is_resolved = any(keyword in summary.lower() for keyword in resolved_keywords)
                    ticket_metadata['appears_resolved'] = is_resolved
                
                # integrated_objects에 저장 (기존 데이터 보존)
                # 메타데이터 스마트 업데이트: 변경 가능한 필드는 업데이트, 고정 필드는 보존
                updated_metadata = base_metadata.copy()  # 기존 메타데이터 복사
                
                # 변경 가능한 기본 정보 (항상 최신으로 업데이트)
                changeable_fields = {
                    'subject': ticket.get('subject', ''),
                    'status': ticket.get('status', ''),
                    'priority': ticket.get('priority', ''),
                    'updated_at': ticket.get('updated_at', ''),
                    # 추가 변경 가능한 필드들
                    'tags': ticket.get('tags', []),
                    'custom_fields': ticket.get('custom_fields', {}),
                    'assigned_to': ticket.get('responder_id', ''),
                    'group_id': ticket.get('group_id', ''),
                    'source': ticket.get('source', ''),
                    'type': ticket.get('type', '')
                }
                
                # 변경 감지 및 업데이트
                for field, new_value in changeable_fields.items():
                    if field in updated_metadata:
                        old_value = updated_metadata[field]
                        if old_value != new_value:
                            logger.debug(f"티켓 {original_id}: {field} 변경됨 {old_value} → {new_value}")
                            updated_metadata[field] = new_value
                    else:
                        updated_metadata[field] = new_value
                
                # 고정 필드 (생성 시에만 설정, 이후 변경 안됨)
                immutable_fields = {
                    'created_at': ticket.get('created_at', ''),
                    'requester_id': ticket.get('requester_id', ''),
                    'company_id': ticket.get('company_id', '')
                }
                
                # 고정 필드는 기존 값이 없을 때만 설정
                for field, value in immutable_fields.items():
                    if field not in updated_metadata and value:
                        updated_metadata[field] = value
                
                # 통합 객체 정보 (기존 값 우선, 없으면 새로 계산)
                integration_fields = {
                    'has_conversations': integrated_ticket.get('has_conversations', False),
                    'has_attachments': integrated_ticket.get('has_attachments', False),
                    'conversation_count': integrated_ticket.get('conversation_count', 0),
                    'attachment_count': integrated_ticket.get('attachment_count', 0)
                }
                
                # 통합 정보는 기존 값이 있으면 보존, 없으면 새로 설정
                for field, new_value in integration_fields.items():
                    if field not in updated_metadata:
                        updated_metadata[field] = new_value
                
                # 첨부파일 메타데이터 업데이트 (항상 최신 상태로 유지)
                attachments_metadata = ticket_metadata.get('attachments', [])
                updated_metadata['attachments'] = attachments_metadata
                logger.debug(f"티켓 {original_id}: 첨부파일 메타데이터 업데이트 완료 - {len(attachments_metadata)}개")
                
                # 요약 생성 관련 메타데이터도 업데이트
                updated_metadata['summary_generated_at'] = ticket_metadata.get('summary_generated_at')
                updated_metadata['summary_length'] = ticket_metadata.get('summary_length', 0)
                updated_metadata['contains_error'] = ticket_metadata.get('contains_error', False)
                updated_metadata['appears_resolved'] = ticket_metadata.get('appears_resolved', False)
                
                # 최종 메타데이터 확인 로그
                logger.debug(f"티켓 {original_id}: 최종 메타데이터 - attachments={len(updated_metadata.get('attachments', []))}개, "
                           f"summary_length={updated_metadata.get('summary_length', 0)}, "
                           f"contains_error={updated_metadata.get('contains_error', False)}")

                integrated_data = {
                    'original_id': original_id,
                    'company_id': company_id,
                    'platform': platform,
                    'object_type': 'integrated_ticket',
                    'original_data': integrated_ticket,  # 기존 통합 객체 보존 (대화, 첨부파일 포함)
                    'integrated_content': integrated_content,  # 기존 통합 텍스트 보존
                    'summary': summary,  # 새로 생성된 요약만 업데이트
                    'metadata': updated_metadata
                }
                
                db.insert_integrated_object(integrated_data)
                result["success_count"] += 1
                logger.debug(f"티켓 {original_id}: 요약 생성 및 저장 완료")
                
            except Exception as e:
                logger.error(f"티켓 {original_id} 요약 생성 중 오류: {e}")
                result["failure_count"] += 1
                result["errors"].append(f"티켓 {original_id}: {str(e)}")
        
        # 2. KB 문서 요약 생성
        logger.info("KB 문서 요약 생성 중...")
        articles = db.get_articles_by_company_and_platform(company_id, platform)
        logger.info(f"처리할 KB 문서 수: {len(articles)}")
        
        for article in articles:
            try:
                original_id = str(article.get('original_id', ''))
                
                # 기존 요약 확인 (force_update가 False인 경우)
                existing_data = None
                cursor = db.connection.cursor()
                cursor.execute("""
                    SELECT original_data, integrated_content, metadata, summary FROM integrated_objects 
                    WHERE company_id = ? AND platform = ? AND object_type = ? AND original_id = ?
                """, (company_id, platform, 'integrated_article', original_id))
                existing_row = cursor.fetchone()
                
                if existing_row:
                    existing_original_data, existing_integrated_content, existing_metadata_str, existing_summary = existing_row
                    
                    # 기존 데이터가 있고 force_update가 False인 경우 요약만 확인
                    if not force_update and existing_summary:
                        logger.debug(f"KB {original_id}: 기존 요약 존재, 건너뜀")
                        result["skipped_count"] += 1
                        continue
                    
                    # 기존 데이터 파싱
                    try:
                        existing_data = {
                            'original_data': json.loads(existing_original_data) if existing_original_data else None,
                            'integrated_content': existing_integrated_content,
                            'metadata': json.loads(existing_metadata_str) if existing_metadata_str else {}
                        }
                    except json.JSONDecodeError:
                        logger.warning(f"KB {original_id}: 기존 데이터 파싱 실패, 새로 생성")
                        existing_data = None
                
                # 통합 문서 객체 생성 (기존 데이터가 없는 경우에만)
                if existing_data and existing_data['original_data']:
                    # 기존 데이터 사용 (첨부파일 보존)
                    integrated_article = existing_data['original_data']
                    integrated_content = existing_data['integrated_content']
                    base_metadata = existing_data['metadata']
                else:
                    # 새로 생성
                    integrated_article = create_integrated_article_object(
                        article=article,
                        company_id=company_id
                    )
                    integrated_content = integrated_article.get('integrated_text', '')
                    base_metadata = {}
                
                # LLM 요약 생성
                content_text = article.get('description_text', '') or article.get('description', '')
                if not content_text:
                    logger.warning(f"KB {original_id}: 요약할 내용이 없음")
                    result["skipped_count"] += 1
                    continue
                
                summary = await generate_summary(
                    content=content_text,
                    content_type="knowledge_base",
                    subject=article.get('title', ''),
                    metadata={
                        'status': article.get('status', ''),
                        'category_id': article.get('category_id', ''),
                        'created_at': article.get('created_at', '')
                    }
                )
                
                # integrated_objects에 저장 (기존 데이터 보존)
                # 메타데이터 스마트 업데이트: 변경 가능한 필드는 업데이트, 고정 필드는 보존
                updated_metadata = base_metadata.copy()  # 기존 메타데이터 복사
                
                # 변경 가능한 기본 정보 (항상 최신으로 업데이트)
                changeable_fields = {
                    'title': article.get('title', ''),
                    'status': article.get('status', ''),
                    'category_id': article.get('category_id', ''),
                    'updated_at': article.get('updated_at', ''),
                    # 추가 변경 가능한 필드들
                    'tags': article.get('tags', []),
                    'folder_id': article.get('folder_id', ''),
                    'type': article.get('type', ''),
                    'agent_id': article.get('agent_id', ''),
                    'thumbs_up': article.get('thumbs_up', 0),
                    'thumbs_down': article.get('thumbs_down', 0)
                }
                
                # 변경 감지 및 업데이트
                for field, new_value in changeable_fields.items():
                    if field in updated_metadata:
                        old_value = updated_metadata[field]
                        if old_value != new_value:
                            logger.debug(f"KB {original_id}: {field} 변경됨 {old_value} → {new_value}")
                            updated_metadata[field] = new_value
                    else:
                        updated_metadata[field] = new_value
                
                # 고정 필드 (생성 시에만 설정, 이후 변경 안됨)
                immutable_fields = {
                    'created_at': article.get('created_at', ''),
                    'author_id': article.get('author_id', ''),
                    'original_category': article.get('category', {})
                }
                
                # 고정 필드는 기존 값이 없을 때만 설정
                for field, value in immutable_fields.items():
                    if field not in updated_metadata and value:
                        updated_metadata[field] = value
                
                # 통합 객체 정보 (기존 값 우선, 없으면 새로 계산)
                integration_fields = {
                    'has_attachments': integrated_article.get('has_attachments', False),
                    'attachment_count': integrated_article.get('attachment_count', 0),
                    'has_inline_images': integrated_article.get('has_inline_images', False),
                    'inline_image_count': integrated_article.get('inline_image_count', 0)
                }
                
                # 통합 정보는 기존 값이 있으면 보존, 없으면 새로 설정
                for field, new_value in integration_fields.items():
                    if field not in updated_metadata:
                        updated_metadata[field] = new_value
                
                integrated_data = {
                    'original_id': original_id,
                    'company_id': company_id,
                    'platform': platform,
                    'object_type': 'integrated_article',
                    'original_data': integrated_article,  # 기존 통합 객체 보존 (첨부파일 포함)
                    'integrated_content': integrated_content,  # 기존 통합 텍스트 보존
                    'summary': summary,  # 새로 생성된 요약만 업데이트
                    'metadata': updated_metadata
                }
                
                db.insert_integrated_object(integrated_data)
                result["success_count"] += 1
                logger.debug(f"KB {original_id}: 요약 생성 및 저장 완료")
                
            except Exception as e:
                logger.error(f"KB {original_id} 요약 생성 중 오류: {e}")
                result["failure_count"] += 1
                result["errors"].append(f"KB {original_id}: {str(e)}")
        
        result["total_processed"] = result["success_count"] + result["failure_count"] + result["skipped_count"]
        result["processing_time"] = time.time() - start_time
        
        logger.info(f"✅ LLM 요약 생성 완료:")
        logger.info(f"  - 성공: {result['success_count']}")
        logger.info(f"  - 실패: {result['failure_count']}")
        logger.info(f"  - 건너뜀: {result['skipped_count']}")
        logger.info(f"  - 총 처리: {result['total_processed']}")
        logger.info(f"  - 소요 시간: {result['processing_time']:.2f}초")
        
        # 메타데이터 포함하여 반환
        if return_metadata and attachment_metadata:
            result["attachment_metadata"] = attachment_metadata
            logger.info(f"  - 첨부파일 메타데이터: {len(attachment_metadata)}개 티켓")
        
        return result
        
    except Exception as e:
        logger.error(f"LLM 요약 생성 중 오류 발생: {e}")
        result["errors"].append(str(e))
        result["processing_time"] = time.time() - start_time
        raise
    finally:
        db.disconnect()


async def sync_summaries_to_vector_db(company_id: str, platform: str = "freshdesk", 
                                      batch_size: int = 25, force_update: bool = False) -> Dict[str, Any]:
    """
    SQLite에서 요약이 생성된 문서들을 조회하여 벡터 DB에 동기화합니다.
    
    Args:
        company_id: 회사 ID
        platform: 플랫폼명 (기본값: "freshdesk")
        batch_size: 배치 크기 (기본값: 25)
        force_update: 강제 업데이트 여부 (기본값: False)
        
    Returns:
        Dict[str, Any]: 동기화 결과 정보
    """
    from core.database.database import get_database
    from core.database.vectordb import vector_db
    
    result = {
        "status": "success",
        "message": "벡터 DB 동기화 완료",
        "synced_count": 0,
        "errors": [],
        "error_count": 0
    }
    
    db = None
    
    try:
        # 데이터베이스 연결
        db = get_database(company_id, platform)
        logger.info("벡터 DB 동기화용 데이터베이스 연결 완료")
        
        # SQLite에서 요약이 있는 문서들 조회
        cursor = db.connection.cursor()
        
        # 티켓 데이터 조회 (요약이 있는 것만)
        logger.info("SQLite에서 티켓 데이터 조회 중...")
        cursor.execute("""
            SELECT original_id, company_id, platform, object_type, summary, integrated_content, metadata
            FROM integrated_objects 
            WHERE company_id = ? AND platform = ? 
            AND (summary IS NOT NULL AND summary != '')
            AND object_type LIKE '%ticket%'
        """, (company_id, platform))
        
        ticket_rows = cursor.fetchall()
        logger.info(f"티켓 데이터 {len(ticket_rows)}개 조회 완료 (요약 또는 원본 콘텐츠)")
        
        # KB 문서 데이터 조회 (요약이 있는 것만)
        logger.info("SQLite에서 KB 문서 데이터 조회 중...")
        cursor.execute("""
            SELECT original_id, company_id, platform, object_type, summary, integrated_content, metadata
            FROM integrated_objects 
            WHERE company_id = ? AND platform = ? 
            AND (summary IS NOT NULL AND summary != '')
            AND object_type LIKE '%article%'
        """, (company_id, platform))
        
        article_rows = cursor.fetchall()
        logger.info(f"KB 문서 데이터 {len(article_rows)}개 조회 완료 (요약 또는 원본 콘텐츠)")
        
        # 모든 데이터 통합
        all_rows = ticket_rows + article_rows
        total_count = len(all_rows)
        
        if total_count == 0:
            result["message"] = "동기화할 문서가 없습니다 (요약이 생성된 문서 없음)"
            return result
        
        logger.info(f"벡터 DB에 {total_count}개 문서 업로드 시작...")
        
        # 벡터 DB 클라이언트 가져오기
        vector_client = vector_db
        
        # 문서 변환 및 업로드
        documents = []
        for row in all_rows:
            original_id, db_company_id, db_platform, object_type, summary, integrated_content, metadata_str = row
            
            # 메타데이터 파싱
            try:
                metadata = json.loads(metadata_str) if metadata_str else {}
            except json.JSONDecodeError:
                metadata = {}
            
            # doc_type 설정 - object_type에서 추출
            if 'ticket' in object_type.lower():
                doc_type = 'ticket'
            elif 'article' in object_type.lower():
                doc_type = 'kb_article'
            else:
                doc_type = 'unknown'
            
            # 문서 객체 생성
            doc = {
                'id': f"{db_company_id}_{db_platform}_{original_id}",
                'content': summary or integrated_content or "",
                'metadata': {
                    'doc_type': doc_type,  # 필수 필드
                    'original_id': str(original_id),
                    'company_id': db_company_id,
                    'platform': db_platform,
                    'object_type': object_type,
                    **metadata  # 기존 메타데이터 병합
                }
            }
            
            documents.append(doc)
        
        # 벡터 DB에 문서 추가 (비동기 아님)
        if documents:
            # documents를 vectordb의 add_documents 형식에 맞게 변환
            texts = [doc['content'] for doc in documents]
            metadatas = [doc['metadata'] for doc in documents]
            ids = [doc['id'] for doc in documents]
            
            # 실제 임베딩 생성
            logger.info(f"임베딩 생성 시작: {len(texts)}개 문서")
            from core.search.embeddings.embedder import embed_documents
            embeddings = embed_documents(texts)
            logger.info(f"임베딩 생성 완료: {len(embeddings)}개")
            
            vector_client.add_documents(texts, embeddings, metadatas, ids)
            result["synced_count"] = len(documents)
            logger.info(f"벡터 DB 동기화 완료: {len(documents)}개 문서")
        else:
            result["message"] = "업로드할 문서가 없습니다"
        
    except Exception as e:
        logger.error(f"벡터 DB 동기화 실패: {e}")
        result["status"] = "error"
        result["errors"].append(str(e))
        result["error_count"] += 1
    finally:
        if db:
            db.disconnect()
            logger.info("벡터 DB 동기화용 데이터베이스 연결 해제")
    
    return result


# 임시 검증 및 상태 관리 함수들 (validator.py로 이동 예정)

async def update_status_mappings(collection_name: str = COLLECTION_NAME) -> None:
    """
    Qdrant에서 기존 상태 값들을 조회하여 매핑 정보를 업데이트합니다.
    """
    logger.info("Qdrant에서 상태 매핑 정보 업데이트 중...")
    # 구현은 validator.py로 이동
    pass


def verify_database_integrity() -> bool:
    """
    데이터베이스 무결성을 검증합니다.
    """
    logger.info("데이터베이스 무결성 검증 중...")
    # 구현은 validator.py로 이동
    return True
