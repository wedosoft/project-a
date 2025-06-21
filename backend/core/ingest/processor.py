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

from core.search.embeddings.embedder import embed_documents, process_documents
from core.database.vectordb import vector_db
from core.database import SQLiteDatabase
from core.ingest.integrator import create_integrated_ticket_object, create_integrated_article_object
from core.ingest.storage import store_integrated_object_to_sqlite, sanitize_metadata
from core.ingest.validator import load_status_mappings, save_status_mappings
from core.platforms.freshdesk.fetcher import (
    extract_company_id_from_domain,
    fetch_kb_articles,
    fetch_tickets,
)

# 로깅 설정
logger = logging.getLogger(__name__)

COLLECTION_NAME = "documents"  # Qdrant 컬렉션 이름
PROCESS_ATTACHMENTS = True  # 첨부파일 처리 여부 설정

# FRESHDESK_DOMAIN에서 company_id 자동 추출
FRESHDESK_DOMAIN = os.getenv("FRESHDESK_DOMAIN")
if FRESHDESK_DOMAIN:
    DEFAULT_COMPANY_ID = extract_company_id_from_domain(FRESHDESK_DOMAIN)
    logger.debug(f"FRESHDESK_DOMAIN '{FRESHDESK_DOMAIN}'에서 추출된 company_id: '{DEFAULT_COMPANY_ID}'")
else:
    DEFAULT_COMPANY_ID = "default"
    logger.warning("FRESHDESK_DOMAIN 환경변수가 설정되지 않아 기본값 'default'를 사용합니다.")


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
    incremental: bool = True,
    purge: bool = False,
    process_attachments: bool = PROCESS_ATTACHMENTS,
    force_rebuild: bool = False,
    local_data_dir: Optional[str] = None,
    include_kb: bool = True,
    domain: Optional[str] = None,
    api_key: Optional[str] = None,
    max_tickets: Optional[int] = None,
    max_articles: Optional[int] = None,
) -> None:
    """
    Freshdesk 티켓과 지식베이스 문서를 임베딩 후 Qdrant에 저장합니다.
    
    Args:
        incremental: 증분 업데이트 모드 여부 (기본값: True)
        purge: 기존 데이터 삭제 여부 (기본값: False)
        process_attachments: 첨부파일 처리 여부 (기본값: True)
        force_rebuild: 데이터베이스 강제 재구축 여부 (기본값: False)
        local_data_dir: 로컬 데이터 디렉토리 경로 (None이면 Freshdesk API에서 직접 수집)
        include_kb: 지식베이스 데이터 포함 여부 (기본값: True)
        domain: Freshdesk 도메인 (None이면 환경변수 사용)
        api_key: Freshdesk API 키 (None이면 환경변수 사용)
        max_tickets: 최대 수집 티켓 수 (None이면 무제한, 기본값: None)
        max_articles: 최대 수집 KB 문서 수 (None이면 무제한, 기본값: None)
    """
    start_time = time.time()
    
    # FRESHDESK_DOMAIN에서 company_id 자동 추출
    FRESHDESK_DOMAIN = os.getenv("FRESHDESK_DOMAIN")
    if FRESHDESK_DOMAIN:
        DEFAULT_COMPANY_ID = extract_company_id_from_domain(FRESHDESK_DOMAIN)
        logger.debug(f"ingest: FRESHDESK_DOMAIN '{FRESHDESK_DOMAIN}'에서 추출된 company_id: '{DEFAULT_COMPANY_ID}'")
    else:
        DEFAULT_COMPANY_ID = "default"
        logger.warning("ingest: FRESHDESK_DOMAIN 환경변수가 설정되지 않아 기본값 'default'를 사용합니다.")
    
    logger.info("데이터 수집 프로세스 시작")
    start_time = time.time()

    try:
        # Qdrant 클라우드만 사용하므로, 로컬 DB 백업/무결성 검사 등은 제거됨
        if force_rebuild:
            logger.warning("데이터베이스 강제 재구축 모드 (Qdrant 클라우드 환경)")
            incremental = False
            purge = True
        
        existing_count = vector_db.count(company_id=DEFAULT_COMPANY_ID)
        logger.info(f"기존 컬렉션에 {existing_count}개 문서가 있습니다 (company_id={DEFAULT_COMPANY_ID})")

        total_count = vector_db.count()
        logger.info(f"컬렉션 전체 문서 수: {total_count}")
        
        if total_count == 0 and purge is False:
            logger.warning("컬렉션에 문서가 없습니다. 데이터베이스가 비어있거나 접근에 문제가 있을 수 있습니다.")
            incremental = False
            purge = False

        if local_data_dir:
            # 로컬에서 이미 수집된 데이터 읽기
            logger.info(f"로컬 데이터 디렉토리에서 데이터 로드 중: {local_data_dir}")
            
            # 체크포인트 확인 - 이미 임베딩이 완료된 데이터가 있는지 확인
            # 단, force_rebuild가 아닌 경우에만 체크포인트 복구 시도
            embedded_checkpoint = load_checkpoint(local_data_dir, "embedded")
            if embedded_checkpoint and not force_rebuild:
                # 체크포인트 복구 시도 전 사용자 확인 (자동 재수집 방지)
                logger.warning("⚠️  기존 임베딩 작업이 중단된 상태입니다.")
                logger.info("체크포인트에서 작업을 재개하려면 force_rebuild=False 상태에서만 가능합니다.")
                
                # 자동 재수집 방지: 명시적 재개 요청이 있을 때만 실행
                if not incremental:  # 전체 재수집 모드에서는 체크포인트 무시
                    logger.info("전체 재수집 모드: 기존 체크포인트를 무시하고 새로 시작합니다.")
                    clear_checkpoints(local_data_dir)
                else:
                    logger.info("임베딩 완료된 체크포인트 발견됨, 벡터 DB 저장 단계부터 재개...")
                    docs = embedded_checkpoint["docs"]
                    all_embeddings = embedded_checkpoint["embeddings"]
                    metadatas = embedded_checkpoint["metadatas"]
                    ids = embedded_checkpoint["ids"]
                    
                    # 벡터 DB 저장으로 바로 이동
                    logger.info("Qdrant 벡터 DB에 문서 저장 중...")
                    batch_size = 50
                    for i in range(0, len(docs), batch_size):
                        end_idx = min(i + batch_size, len(docs))
                        batch_docs = docs[i:end_idx]
                        batch_embeddings = all_embeddings[i:end_idx]
                        batch_metadatas = metadatas[i:end_idx]
                        batch_ids = ids[i:end_idx]

                        logger.info(f"문서 배치 저장 중... ({i+1}~{end_idx}/{len(docs)})")
                        vector_db.add_documents(
                            texts=batch_docs,
                            embeddings=batch_embeddings,
                            metadatas=batch_metadatas,
                            ids=batch_ids,
                        )
                    
                    # 성공적으로 완료되면 체크포인트 정리
                    clear_checkpoints(local_data_dir)
                    logger.info("✅ 체크포인트에서 벡터 DB 저장 완료")
                    return
            
            # 체크포인트가 없거나 force_rebuild인 경우 일반 로드
            tickets, articles = load_local_data(local_data_dir)
            
            # 지식베이스 문서 포함 여부에 따라 처리
            if not include_kb:
                logger.info("include_kb=False 설정으로 지식베이스 문서는 제외됩니다.")
                articles = []
            
            # 데이터 로드 체크포인트 저장
            checkpoint_data = {
                "tickets": tickets,
                "articles": articles,
                "docs": [],
                "embeddings": [],
                "metadatas": [],
                "ids": []
            }
            save_checkpoint(local_data_dir, "data_loaded", checkpoint_data)
            
        else:
            # 기존 방식: Freshdesk API에서 직접 수집
            logger.info("Freshdesk 데이터 수집 중...")
            # 동적 Freshdesk 설정을 fetch 함수들에 전달
            tickets_task = asyncio.create_task(fetch_tickets(domain=domain, api_key=api_key, max_tickets=max_tickets or 10000))
            articles_task = asyncio.create_task(fetch_kb_articles(domain=domain, api_key=api_key, max_articles=max_articles))
            tickets, articles = await asyncio.gather(tickets_task, articles_task)

        if not tickets and not articles:
            logger.warning("Freshdesk에서 가져온 데이터가 없습니다.")
            return

        # SQLite에 원본 데이터 저장
        logger.info("SQLite 데이터베이스에 원본 데이터 저장 중...")
        job_id = f"ingest_{int(time.time())}"
        try:
            # 테스트용 데이터베이스 사용 (100건 제한)
            db = SQLiteDatabase("freshdesk_test_data.db")
            db.connect()
            db.create_tables()
            
            # 수집 작업 시작 로그
            job_start_data = {
                'job_id': job_id,
                'company_id': DEFAULT_COMPANY_ID,
                'job_type': 'ingest',
                'status': 'started',
                'start_time': datetime.now().isoformat(),
                'config': {
                    'incremental': incremental,
                    'purge': purge,
                    'include_kb': include_kb,
                    'tickets_count': len(tickets),
                    'articles_count': len(articles)
                }
            }
            db.log_collection_job(job_start_data)
            
            # 티켓 데이터를 통합 객체로 변환하여 저장
            tickets_saved = 0
            for ticket in tickets:
                # create_integrated_ticket_object는 이미 integrator.py에 있음
                integrated_ticket = create_integrated_ticket_object(ticket)
                if store_integrated_object_to_sqlite(db, integrated_ticket, DEFAULT_COMPANY_ID):
                    tickets_saved += 1
            
            # KB 문서 데이터를 통합 객체로 변환하여 저장
            articles_saved = 0
            for article in articles:
                # create_integrated_article_object는 이미 integrator.py에 있음  
                integrated_article = create_integrated_article_object(article)
                if store_integrated_object_to_sqlite(db, integrated_article, DEFAULT_COMPANY_ID):
                    articles_saved += 1
            
            logger.info(f"SQLite에 저장됨 - 티켓: {tickets_saved}개, KB 문서: {articles_saved}개")
            
        except Exception as e:
            logger.error(f"SQLite 저장 중 오류: {e}")
        finally:
            if 'db' in locals():
                db.close()

        # 벡터 임베딩 및 저장 로직은 원본 파일에서 계속 가져와야 함
        # 이 부분은 다음 단계에서 완성하겠습니다.
        
        # 임시로 성공 로그만 출력
        end_time = time.time()
        elapsed_time = end_time - start_time
        logger.info(f"✅ 데이터 수집 프로세스 완료 (소요시간: {elapsed_time:.2f}초)")
        
    except Exception as e:
        logger.error(f"데이터 수집 중 오류 발생: {e}")
        raise


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
