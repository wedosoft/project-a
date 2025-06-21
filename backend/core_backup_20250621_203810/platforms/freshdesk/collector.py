# -*- coding: utf-8 -*-
"""
Freshdesk 데이터 수집기
기존 optimized_fetcher.py를 Freshdesk 전용으로 특화하여 구현
"""

import asyncio
import json
import logging
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from dotenv import load_dotenv

from .adapter import FreshdeskAdapter
# 통합 객체 생성을 위한 모듈 추가
from ...data_merger import PlatformDataMerger, DataStorage

# .env 파일 로드
load_dotenv()

logger = logging.getLogger(__name__)


class FreshdeskCollector:
    """
    Freshdesk 전용 데이터 수집기
    기존 OptimizedFreshdeskFetcher의 구조와 로직을 최대한 재활용
    """
    
    def __init__(self, config: Dict[str, Any], output_dir: str = "freshdesk_data"):
        """
        Args:
            config: Freshdesk 설정 딕셔너리
                - domain: Freshdesk 도메인
                - api_key: API 키
                - company_id: 회사 식별자
            output_dir: 데이터 저장 디렉토리
        """
        self.config = config
        self.company_id = config.get("company_id")
        
        if not self.company_id:
            raise ValueError("company_id는 필수 설정값입니다")
        
        # 회사별 디렉토리 구조: {output_dir}/{company_id}/
        output_path = Path(output_dir)
        if not output_path.is_absolute():
            # backend/ 하위로 강제
            backend_root = Path(__file__).parent.parent.parent.parent
            output_path = backend_root / output_path
        
        self.output_dir = output_path.resolve() / self.company_id
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 하위 디렉토리 생성 (raw 데이터 저장용) - 기존 구조 유지
        self.raw_data_dir = self.output_dir / "raw_data"
        self.raw_data_dir.mkdir(exist_ok=True)
        
        # 세부 raw 데이터 디렉토리 생성 - 기존 구조 동일
        (self.raw_data_dir / "tickets").mkdir(exist_ok=True)
        (self.raw_data_dir / "ticket_details").mkdir(exist_ok=True)
        (self.raw_data_dir / "conversations").mkdir(exist_ok=True)
        (self.raw_data_dir / "attachments").mkdir(exist_ok=True)
        (self.raw_data_dir / "knowledge_base").mkdir(exist_ok=True)
        
        # 통합 데이터 저장용 디렉토리 추가
        self.merged_data_dir = self.output_dir / "merged_data"
        self.merged_data_dir.mkdir(exist_ok=True)
        
        self.progress_file = self.output_dir / "progress.json"
        
        # Freshdesk 어댑터 인스턴스
        self.adapter: Optional[FreshdeskAdapter] = None
        
        # 데이터 병합기 및 저장소 인스턴스
        self.data_merger = PlatformDataMerger(platform="freshdesk", company_id=self.company_id)
        self.data_storage = DataStorage(storage_type="file", base_path=self.merged_data_dir)
        
        # 기존 OptimizedFreshdeskFetcher의 설정값들 재사용
        self.MAX_RETRIES = config.get("max_retries", 5)
        self.RETRY_DELAY = config.get("retry_delay", 2) 
        self.PER_PAGE = config.get("per_page", 100)
        self.REQUEST_DELAY = config.get("request_delay", 0.3)
        self.CHUNK_SIZE = config.get("chunk_size", 10000)
        self.SAVE_INTERVAL = config.get("save_interval", 1000)
        self.RAW_DATA_CHUNK_SIZE = config.get("raw_data_chunk_size", 1000)
        self.KB_CHUNK_SIZE = config.get("kb_chunk_size", 500)
        
        logger.info(f"Freshdesk 수집기 초기화: company_id={self.company_id}")
    
    async def __aenter__(self):
        """Async context manager 진입"""
        self.adapter = FreshdeskAdapter(self.config)
        await self.adapter.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager 종료"""
        if self.adapter:
            await self.adapter.__aexit__(exc_type, exc_val, exc_tb)
    
    def _save_progress(self, data: Dict):
        """진행상황 저장 (기존 로직 재사용)"""
        try:
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"진행상황 저장 실패: {e}")
    
    def _load_progress(self) -> Dict:
        """진행상황 로드 (기존 로직 재사용)"""
        try:
            if self.progress_file.exists():
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"진행상황 로드 실패: {e}")
        
        return {}
    
    def _save_raw_data_chunk(self, data_type: str, data: List[Dict], chunk_index: int):
        """Raw 데이터 청크 저장 (기존 로직 재사용)"""
        try:
            filename = f"{data_type}_chunk_{chunk_index:04d}.json"
            filepath = self.raw_data_dir / data_type / filename
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"{data_type} 청크 {chunk_index} 저장완료: {len(data)}개 항목")
            
        except Exception as e:
            logger.error(f"{data_type} 청크 저장 실패: {e}")
    
    async def collect_tickets(self, 
                            since_date: Optional[str] = None, 
                            until_date: Optional[str] = None,
                            include_details: bool = True,
                            include_conversations: bool = True,
                            include_attachments: bool = True) -> Dict[str, Any]:
        """
        티켓 데이터 수집 (기존 로직 재사용하면서 어댑터 사용)
        """
        if not self.adapter:
            raise RuntimeError("어댑터가 초기화되지 않았습니다. async with 구문을 사용하세요.")
        
        logger.info("티켓 데이터 수집 시작")
        start_time = datetime.now()
        
        progress = self._load_progress()
        collected_tickets = []
        total_processed = 0
        chunk_index = 0
        
        try:
            # 1. 기본 티켓 목록 수집
            logger.info("기본 티켓 목록 수집 중...")
            tickets = await self.adapter.fetch_tickets(
                since_date=since_date, 
                include_attachments=include_attachments
            )
            
            # until_date 필터링
            if until_date:
                tickets = [t for t in tickets if t.get('updated_at', '') <= until_date]
            
            logger.info(f"기본 티켓 목록 수집 완료: {len(tickets)}개")
            
            # 2. 티켓별 세부 정보 수집 및 통합 객체 생성
            merged_documents = []  # 통합 문서 리스트
            
            for i, ticket in enumerate(tickets):
                ticket_id = ticket.get('id')
                
                try:
                    # 상세 정보 수집
                    conversations = []
                    attachments = []
                    
                    if include_details:
                        detail = await self.adapter.fetch_ticket_details(ticket_id)
                        if detail:
                            ticket.update(detail)
                    
                    # 대화 내역 수집
                    if include_conversations:
                        conversations = await self.adapter.fetch_conversations(ticket_id)
                        ticket['conversations'] = conversations
                    
                    # 첨부파일 정보 수집
                    if include_attachments:
                        attachments = await self.adapter.fetch_attachments(ticket_id)
                        ticket['attachments'] = attachments
                    
                    # Raw 데이터 저장 (기존 방식 유지)
                    collected_tickets.append(ticket)
                    
                    # 통합 객체 생성 및 저장
                    try:
                        merged_document = self.data_merger.merge_ticket_data(
                            ticket=ticket,
                            conversations=conversations,
                            attachments=attachments
                        )
                        
                        # 통합 문서 유효성 검증
                        if self.data_merger.validate_merged_document(merged_document):
                            # 통합 객체 저장
                            await self.data_storage.save_merged_document(
                                platform="freshdesk",
                                company_id=self.company_id,
                                document=merged_document,
                                doc_type="ticket"
                            )
                            merged_documents.append(merged_document)
                            logger.debug(f"티켓 {ticket_id} 통합 객체 생성 완료")
                        else:
                            logger.warning(f"티켓 {ticket_id} 통합 객체 유효성 검증 실패")
                            
                    except Exception as merge_error:
                        logger.error(f"티켓 {ticket_id} 통합 객체 생성 실패: {merge_error}")
                        # 통합 객체 생성 실패해도 Raw 데이터는 보존
                    
                    total_processed += 1
                    
                    # 주기적으로 청크 저장 (Raw 데이터)
                    if len(collected_tickets) >= self.RAW_DATA_CHUNK_SIZE:
                        self._save_raw_data_chunk("tickets", collected_tickets, chunk_index)
                        chunk_index += 1
                        collected_tickets = []
                    
                    # 진행상황 업데이트
                    if total_processed % self.SAVE_INTERVAL == 0:
                        progress.update({
                            "last_processed_ticket": ticket_id,
                            "processed_count": total_processed,
                            "merged_documents_count": len(merged_documents),
                            "last_update": datetime.now().isoformat()
                        })
                        self._save_progress(progress)
                        logger.info(f"티켓 처리 진행: {total_processed}/{len(tickets)} (통합객체: {len(merged_documents)}개)")
                    
                except Exception as e:
                    logger.error(f"티켓 {ticket_id} 처리 중 오류: {e}")
                    continue
            
            # 마지막 청크 저장
            if collected_tickets:
                self._save_raw_data_chunk("tickets", collected_tickets, chunk_index)
            
            # 최종 진행상황 저장
            end_time = datetime.now()
            final_progress = {
                "collection_type": "tickets",
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": (end_time - start_time).total_seconds(),
                "total_processed": total_processed,
                "total_chunks": chunk_index + 1 if collected_tickets or total_processed > 0 else chunk_index,
                "include_details": include_details,
                "include_conversations": include_conversations,
                "include_attachments": include_attachments,
                "since_date": since_date,
                "until_date": until_date
            }
            
            self._save_progress(final_progress)
            
            logger.info(f"티켓 수집 완료: {total_processed}개 처리, 소요시간: {final_progress['duration_seconds']:.2f}초")
            return final_progress
            
        except Exception as e:
            logger.error(f"티켓 수집 중 오류 발생: {e}")
            raise
    
    async def collect_knowledge_base(self, 
                                   category_id: Optional[str] = None,
                                   max_articles: Optional[int] = None) -> Dict[str, Any]:
        """
        지식베이스 수집 (기존 로직 재사용하면서 어댑터 사용)
        """
        if not self.adapter:
            raise RuntimeError("어댑터가 초기화되지 않았습니다. async with 구문을 사용하세요.")
        
        logger.info("지식베이스 수집 시작")
        start_time = datetime.now()
        
        try:
            # 지식베이스 아티클 수집
            articles = await self.adapter.fetch_kb_articles()
            
            # 최대 개수 제한
            if max_articles and len(articles) > max_articles:
                articles = articles[:max_articles]
            
            # 청크별로 저장
            chunk_index = 0
            chunk_data = []
            
            for article in articles:
                chunk_data.append(article)
                
                if len(chunk_data) >= self.KB_CHUNK_SIZE:
                    self._save_raw_data_chunk("knowledge_base", chunk_data, chunk_index)
                    chunk_index += 1
                    chunk_data = []
            
            # 마지막 청크 저장
            if chunk_data:
                self._save_raw_data_chunk("knowledge_base", chunk_data, chunk_index)
            
            # 최종 진행상황 저장
            end_time = datetime.now()
            final_progress = {
                "collection_type": "knowledge_base",
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": (end_time - start_time).total_seconds(),
                "total_articles": len(articles),
                "total_chunks": chunk_index + 1 if chunk_data or len(articles) > 0 else chunk_index,
                "category_id": category_id,
                "max_articles": max_articles
            }
            
            self._save_progress(final_progress)
            
            logger.info(f"지식베이스 수집 완료: {len(articles)}개 처리, 소요시간: {final_progress['duration_seconds']:.2f}초")
            return final_progress
            
        except Exception as e:
            logger.error(f"지식베이스 수집 중 오류 발생: {e}")
            raise
    
    async def full_collection(self, 
                             since_date: Optional[str] = None,
                             until_date: Optional[str] = None,
                             include_kb: bool = True) -> Dict[str, Any]:
        """
        전체 데이터 수집 (기존 로직 재사용)
        """
        logger.info("전체 데이터 수집 시작")
        start_time = datetime.now()
        
        results = {
            "start_time": start_time.isoformat(),
            "collections": {}
        }
        
        try:
            # 1. 티켓 데이터 수집
            logger.info("=== 티켓 데이터 수집 시작 ===")
            ticket_result = await self.collect_tickets(
                since_date=since_date,
                until_date=until_date,
                include_details=True,
                include_conversations=True,
                include_attachments=True
            )
            results["collections"]["tickets"] = ticket_result
            
            # 2. 지식베이스 수집
            if include_kb:
                logger.info("=== 지식베이스 수집 시작 ===")
                kb_result = await self.collect_knowledge_base()
                results["collections"]["knowledge_base"] = kb_result
            
            # 최종 결과
            end_time = datetime.now()
            results.update({
                "end_time": end_time.isoformat(),
                "total_duration_seconds": (end_time - start_time).total_seconds(),
                "success": True
            })
            
            # 최종 진행상황 저장
            self._save_progress(results)
            
            logger.info(f"전체 데이터 수집 완료: 소요시간 {results['total_duration_seconds']:.2f}초")
            return results
            
        except Exception as e:
            logger.error(f"전체 데이터 수집 중 오류: {e}")
            results.update({
                "end_time": datetime.now().isoformat(),
                "error": str(e),
                "success": False
            })
            self._save_progress(results)
            raise


async def main():
    """테스트 및 개발용 메인 함수"""
    # 환경변수에서 설정 로드
    config = {
        "domain": os.getenv("FRESHDESK_DOMAIN"),
        "api_key": os.getenv("FRESHDESK_API_KEY"),
        "company_id": os.getenv("COMPANY_ID", "default_company"),
        "max_retries": 5,
        "per_page": 100,
        "request_delay": 0.3
    }
    
    if not config["domain"] or not config["api_key"]:
        logger.error("FRESHDESK_DOMAIN과 FRESHDESK_API_KEY 환경변수가 필요합니다")
        return
    
    async with FreshdeskCollector(config, "freshdesk_test_data") as collector:
        # 최근 7일간 데이터 수집
        since_date = (datetime.now() - timedelta(days=7)).isoformat()
        
        result = await collector.full_collection(
            since_date=since_date,
            include_kb=True
        )
        
        print(f"수집 결과: {json.dumps(result, ensure_ascii=False, indent=2)}")


if __name__ == "__main__":
    asyncio.run(main())
