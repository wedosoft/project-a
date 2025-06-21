"""
멀티플랫폼 데이터 수집기
기존 optimized_fetcher.py를 멀티플랫폼/멀티테넌트 구조로 리팩토링

기존 코드 90% 이상 재활용하면서 플랫폼 어댑터 패턴 적용
"""

import asyncio
import json
import logging
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Type
from dotenv import load_dotenv

from .platform_adapter import PlatformAdapter
from .freshdesk_adapter import FreshdeskAdapter

# .env 파일 로드
load_dotenv()

# 공통 로깅 모듈 사용 (core/logger.py)
from core.logger import get_logger

logger = get_logger(__name__)


class MultiPlatformDataCollector:
    """
    멀티플랫폼/멀티테넌트 데이터 수집기
    기존 OptimizedFreshdeskFetcher의 구조와 로직을 최대한 재활용하면서
    플랫폼 어댑터 패턴을 통해 멀티플랫폼 지원
    """
    
    # 플랫폼별 어댑터 클래스 매핑
    PLATFORM_ADAPTERS: Dict[str, Type[PlatformAdapter]] = {
        "freshdesk": FreshdeskAdapter,
        # 향후 추가: "zendesk": ZendeskAdapter, "servicenow": ServiceNowAdapter
    }
    
    def __init__(self, config: Dict[str, Any], output_dir: str = "multi_platform_data"):
        """
        Args:
            config: 플랫폼 설정 딕셔너리
                - platform: 플랫폼 이름 (freshdesk, zendesk 등)
                - company_id: 테넌트 식별자
                - domain: 플랫폼 도메인
                - api_key: API 키
                - 기타 플랫폼별 설정
            output_dir: 데이터 저장 디렉토리 기본 경로
        """
        self.config = config
        self.platform = config.get("platform")
        self.company_id = config.get("company_id")
        
        if not self.platform or not self.company_id:
            raise ValueError("platform과 company_id는 필수 설정값입니다")
        
        if self.platform not in self.PLATFORM_ADAPTERS:
            raise ValueError(f"지원하지 않는 플랫폼: {self.platform}. 지원 플랫폼: {list(self.PLATFORM_ADAPTERS.keys())}")
        
        # 플랫폼별 디렉토리 구조: {output_dir}/{platform}/{company_id}/
        output_path = Path(output_dir)
        if not output_path.is_absolute():
            # backend/ 하위로 강제
            backend_root = Path(__file__).parent.parent
            output_path = backend_root / output_path
        
        self.output_dir = output_path.resolve() / self.platform / self.company_id
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
        
        self.progress_file = self.output_dir / "progress.json"
        
        # 플랫폼 어댑터 인스턴스
        self.adapter: Optional[PlatformAdapter] = None
        
        # 기존 OptimizedFreshdeskFetcher의 설정값들 재사용
        self.MAX_RETRIES = config.get("max_retries", 5)
        self.RETRY_DELAY = config.get("retry_delay", 2) 
        self.PER_PAGE = config.get("per_page", 100)
        self.REQUEST_DELAY = config.get("request_delay", 0.3)
        self.CHUNK_SIZE = config.get("chunk_size", 10000)
        self.SAVE_INTERVAL = config.get("save_interval", 1000)
        self.RAW_DATA_CHUNK_SIZE = config.get("raw_data_chunk_size", 1000)
        self.KB_CHUNK_SIZE = config.get("kb_chunk_size", 500)
        
        logger.info(f"멀티플랫폼 수집기 초기화: platform={self.platform}, company_id={self.company_id}")
        logger.info(f"데이터 저장 경로: {self.output_dir}")
    
    async def __aenter__(self):
        """Async context manager 진입"""
        # 플랫폼별 어댑터 초기화
        adapter_class = self.PLATFORM_ADAPTERS[self.platform]
        self.adapter = adapter_class(self.config)
        await self.adapter.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager 종료"""
        if self.adapter:
            await self.adapter.__aexit__(exc_type, exc_val, exc_tb)
    
    # ========== 기존 OptimizedFreshdeskFetcher의 progress 관리 메서드들 재사용 ==========
    
    def save_progress(self, progress_data: Dict):
        """
        진행 상황을 파일에 저장
        기존 OptimizedFreshdeskFetcher.save_progress와 동일
        """
        # 플랫폼 및 테넌트 정보 추가
        progress_data.update({
            "platform": self.platform,
            "company_id": self.company_id,
            "last_updated_timestamp": datetime.now().isoformat()
        })
        
        with open(self.progress_file, 'w') as f:
            json.dump(progress_data, f, indent=2)
    
    def load_progress(self) -> Dict:
        """
        저장된 진행 상황 로드
        기존 OptimizedFreshdeskFetcher.load_progress와 거의 동일
        """
        if self.progress_file.exists():
            with open(self.progress_file, 'r') as f:
                progress = json.load(f)
                logger.info(f"기존 진행 상황 로드: {progress.get('total_collected', 0):,}개 티켓, {len(progress.get('completed_ranges', []))}개 날짜 범위 완료")
                return progress
        
        # 기본 진행 정보 생성 - 플랫폼 정보 추가
        return {
            "platform": self.platform,
            "company_id": self.company_id,
            "last_updated": None,
            "last_updated_timestamp": None,
            "total_collected": 0,
            "completed_ranges": [],  # 완료된 날짜 범위 목록
            "range_details": {},     # 각 범위별 세부 정보 (티켓 수, 마지막 페이지 등)
            "chunks_completed": [],
            # RAW 데이터 수집 진행 상황 추가
            "raw_data_progress": {
                "ticket_details_chunks": [],
                "conversations_chunks": [],
                "attachments_chunks": [],
                "knowledge_base_chunks": [],
                "last_kb_update": None
            }
        }
    
    def get_date_ranges(self, start_date: Optional[str] = None, end_date: Optional[str] = None, days_per_chunk: int = 30) -> List[tuple]:
        """
        날짜 범위를 분할하여 반환
        기존 OptimizedFreshdeskFetcher.get_date_ranges와 동일
        """
        # start_date가 None이면 현재부터 10년 전으로 설정
        if start_date is None:
            ten_years_ago = datetime.now() - timedelta(days=365 * 10)
            start_date = ten_years_ago.strftime("%Y-%m-%d")
            
        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")
            
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        
        ranges = []
        current = start
        
        # 날짜가 너무 오래된 경우 경고 표시
        days_total = (end - start).days
        if days_total > 365 * 5:  # 5년 이상
            logger.warning(f"매우 긴 기간({days_total}일, {days_total/365:.1f}년)의 티켓을 수집합니다. 시간이 오래 걸릴 수 있습니다.")
            logger.warning(f"총 {days_total / days_per_chunk:.0f}개의 날짜 범위로 분할됩니다.")
        
        while current < end:
            # 종료 날짜는 현재 날짜 + days_per_chunk - 1 (당일 포함)이거나, end 중 더 이른 날짜
            range_end = min(current + timedelta(days=days_per_chunk - 1), end)
            ranges.append((
                current.strftime("%Y-%m-%dT00:00:00Z"),
                range_end.strftime("%Y-%m-%dT23:59:59Z")
            ))
            current = range_end + timedelta(days=1)
            
        logger.info(f"총 {len(ranges)}개의 날짜 범위로 분할되었습니다. ({start_date} ~ {end_date}, {days_per_chunk}일 단위)")
        return ranges
    
    # ========== 기존 OptimizedFreshdeskFetcher의 raw 데이터 저장 메서드들 재사용 ==========
    
    async def save_raw_data_chunk(self, data: List[Dict], data_type: str, chunk_id: str) -> None:
        """
        Raw 데이터를 청크 단위로 저장
        기존 OptimizedFreshdeskFetcher.save_raw_data_chunk와 동일
        """
        # 디버깅: 함수 진입 및 파라미터 로깅
        logger.info(f"🔍 [DEBUG] save_raw_data_chunk 함수 진입")
        logger.info(f"🔍 [DEBUG] 파라미터 - data_type: {data_type}, chunk_id: {chunk_id}, data 항목 수: {len(data) if data else 0}")
        logger.info(f"🔍 [DEBUG] self.raw_data_dir: {self.raw_data_dir}")
        
        if not data:
            logger.warning(f"⚠️ {data_type} 청크 {chunk_id}: 저장할 데이터가 없습니다")
            return
            
        # 디렉토리 생성
        data_type_dir = self.raw_data_dir / data_type
        data_type_dir.mkdir(exist_ok=True)
        logger.info(f"🔍 [DEBUG] 디렉토리 생성/확인: {data_type_dir}")
        
        # 파일 경로 생성 - 플랫폼별 접두사 추가
        chunk_file = data_type_dir / f"{self.platform}_{data_type}_chunk_{chunk_id}.json"
        logger.info(f"🔍 [DEBUG] 저장할 파일 경로: {chunk_file}")
        
        # 데이터 샘플 로깅 (디버깅용)
        if data:
            sample_item = data[0]
            if isinstance(sample_item, dict):
                keys = list(sample_item.keys())[:5]  # 처음 5개 키만
                logger.debug(f"데이터 샘플 키: {keys}...")
        
        try:
            logger.info(f"🔍 [DEBUG] 파일 쓰기 시작: {chunk_file}")
            with open(chunk_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            # 저장 완료 후 파일 크기 확인
            file_size = chunk_file.stat().st_size
            logger.info(f"✅ {data_type} 청크 {chunk_id} 저장 완료: {len(data)}개 항목 → {chunk_file} ({file_size:,} bytes)")
            logger.info(f"🔍 [DEBUG] save_raw_data_chunk 함수 정상 완료")
            
        except Exception as e:
            logger.error(f"❌ {data_type} 청크 {chunk_id} 저장 실패: {e}")
            logger.error(f"🔍 [DEBUG] save_raw_data_chunk 함수 예외 발생: {type(e).__name__}: {e}")
            raise
    
    def save_tickets_chunk(self, tickets: List[Dict], chunk_id: str):
        """
        티켓 청크를 저장 - raw_data/tickets/ 디렉토리에만 저장
        기존 OptimizedFreshdeskFetcher.save_tickets_chunk와 거의 동일 (플랫폼 정보 추가)
        """
        if not tickets:
            logger.warning(f"빈 티켓 리스트로 인해 청크 {chunk_id} 저장을 건너뜁니다.")
            return
            
        # raw_data/tickets/ 디렉토리에 청크 파일 저장 - 플랫폼별 접두사 추가
        tickets_dir = self.raw_data_dir / "tickets"
        tickets_dir.mkdir(parents=True, exist_ok=True)  # 디렉토리 생성 보장
        raw_chunk_file = tickets_dir / f"{self.platform}_tickets_chunk_{chunk_id}.json"
        
        # 임시로 JSON 크기 계산 (메모리에서)
        temp_json = json.dumps(tickets, ensure_ascii=False, indent=2)
        file_size_mb = len(temp_json.encode('utf-8')) / (1024 * 1024)
        
        # 크기 경고 로깅 (50MB 이상 시)
        if file_size_mb > 50:
            logger.warning(f"큰 청크 파일 생성됨: {file_size_mb:.1f}MB (티켓 {len(tickets)}개)")
            logger.warning(f"향후 청크 크기 조정을 고려하세요 (현재 RAW_DATA_CHUNK_SIZE: {self.RAW_DATA_CHUNK_SIZE})")
        
        with open(raw_chunk_file, 'w', encoding='utf-8') as f:
            f.write(temp_json)
        
        logger.info(json.dumps({
            "event": "ticket_chunk_saved",
            "platform": self.platform,
            "company_id": self.company_id,
            "chunk_id": chunk_id,
            "ticket_count": len(tickets),
            "file_size_mb": round(file_size_mb, 2),
            "file_path": str(raw_chunk_file)
        }, ensure_ascii=False))
        logger.info(f"  → 저장 경로: {raw_chunk_file} ({file_size_mb:.1f}MB)")
    
    # ========== 기존 OptimizedFreshdeskFetcher의 데이터 수집 메서드들 어댑터 패턴으로 리팩토링 ==========
    
    async def collect_raw_ticket_details(self, ticket_ids: List[str], progress: Dict) -> int:
        """
        티켓 상세정보를 raw 형태로 수집하여 저장
        기존 OptimizedFreshdeskFetcher.collect_raw_ticket_details를 어댑터 패턴으로 수정
        """
        if not ticket_ids:
            logger.warning("티켓 ID 리스트가 비어있어 상세정보 수집을 건너뜁니다.")
            return 0
            
        logger.info(f"🔍 [DEBUG] collect_raw_ticket_details 시작 - 총 티켓 수: {len(ticket_ids)}")
        logger.info(f"🔍 [DEBUG] self.raw_data_dir: {self.raw_data_dir}")
        logger.info(f"🔍 [DEBUG] RAW_DATA_CHUNK_SIZE: {self.RAW_DATA_CHUNK_SIZE}")
        
        target_dir = self.raw_data_dir / "ticket_details"
        target_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"티켓 상세정보 저장 디렉토리 준비 완료: {target_dir}")
        
        chunk_counter = len(progress.get("raw_data_progress", {}).get("ticket_details_chunks", []))
        current_chunk = []
        success_count = 0
        error_count = 0
        
        for i, ticket_id in enumerate(ticket_ids):
            try:
                # 어댑터를 통해 티켓 상세정보 조회 (정규화 적용됨)
                detail = await self.adapter.fetch_ticket_details(str(ticket_id))
                if detail:
                    current_chunk.append(detail)
                    success_count += 1
                else:
                    error_count += 1
                    logger.warning(f"티켓 {ticket_id} 상세정보가 None으로 반환됨")
            except Exception as e:
                error_count += 1
                logger.error(f"티켓 {ticket_id} 상세정보 수집 중 예외 발생: {e}")
            
            # 청크 크기에 도달하면 저장
            if len(current_chunk) >= self.RAW_DATA_CHUNK_SIZE:
                chunk_id = f"{chunk_counter:04d}"
                logger.info(f"티켓 상세정보 청크 {chunk_id} 저장 중: {len(current_chunk)}개 항목")
                await self.save_raw_data_chunk(current_chunk, "ticket_details", chunk_id)
                progress.setdefault("raw_data_progress", {}).setdefault("ticket_details_chunks", []).append(chunk_id)
                chunk_counter += 1
                current_chunk = []
                
                # 진행 상황 저장
                self.save_progress(progress)
            
            if (i + 1) % 100 == 0:
                logger.info(f"티켓 상세정보 수집 진행률: {i+1}/{len(ticket_ids)} (성공: {success_count}, 실패: {error_count})")
        
        # 마지막 청크 저장
        if current_chunk:
            chunk_id = f"{chunk_counter:04d}"
            logger.info(f"티켓 상세정보 마지막 청크 {chunk_id} 저장 중: {len(current_chunk)}개 항목")
            await self.save_raw_data_chunk(current_chunk, "ticket_details", chunk_id)
            progress.setdefault("raw_data_progress", {}).setdefault("ticket_details_chunks", []).append(chunk_id)
        
        logger.info(f"티켓 상세정보 수집 완료: {success_count}개 성공, {error_count}개 실패")
        return success_count
    
    async def collect_raw_conversations(self, ticket_ids: List[str], progress: Dict) -> int:
        """
        티켓 대화내역을 raw 데이터로 수집하여 저장
        기존 OptimizedFreshdeskFetcher.collect_raw_conversations를 어댑터 패턴으로 수정
        """
        logger.info(f"티켓 대화내역 raw 데이터 수집 시작: {len(ticket_ids)}개")
        
        # 디렉토리 생성 및 초기 파일 준비
        target_dir = self.raw_data_dir / "conversations"
        target_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"대화내역 저장 디렉토리 준비 완료: {target_dir}")
        
        chunk_counter = len(progress.get("raw_data_progress", {}).get("conversations_chunks", []))
        current_chunk = []
        success_count = 0
        error_count = 0
        total_conversations = 0
        
        for i, ticket_id in enumerate(ticket_ids):
            try:
                # 어댑터를 통해 대화내역 조회 (정규화 적용됨)
                conversations = await self.adapter.fetch_conversations(str(ticket_id))
                if conversations:
                    current_chunk.extend(conversations)
                    success_count += 1
                    total_conversations += len(conversations)
                    logger.debug(f"티켓 {ticket_id}: {len(conversations)}개 대화내역")
                else:
                    logger.debug(f"티켓 {ticket_id}: 대화내역 없음")
            except Exception as e:
                error_count += 1
                logger.error(f"티켓 {ticket_id} 대화내역 수집 중 예외 발생: {e}")
            
            # 청크 크기에 도달하면 저장
            if len(current_chunk) >= self.RAW_DATA_CHUNK_SIZE:
                chunk_id = f"{chunk_counter:04d}"
                logger.info(f"대화내역 청크 {chunk_id} 저장 중: {len(current_chunk)}개 항목")
                await self.save_raw_data_chunk(current_chunk, "conversations", chunk_id)
                progress.setdefault("raw_data_progress", {}).setdefault("conversations_chunks", []).append(chunk_id)
                chunk_counter += 1
                current_chunk = []
                
                # 진행 상황 저장
                self.save_progress(progress)
            
            if (i + 1) % 100 == 0:
                logger.info(f"대화내역 수집 진행률: {i+1}/{len(ticket_ids)} (성공: {success_count}, 실패: {error_count}, 총 대화: {total_conversations})")
        
        # 마지막 청크 저장
        if current_chunk:
            chunk_id = f"{chunk_counter:04d}"
            logger.info(f"대화내역 마지막 청크 {chunk_id} 저장 중: {len(current_chunk)}개 항목")
            await self.save_raw_data_chunk(current_chunk, "conversations", chunk_id)
            progress.setdefault("raw_data_progress", {}).setdefault("conversations_chunks", []).append(chunk_id)
        
        logger.info(f"티켓 대화내역 raw 데이터 수집 완료: 총 {success_count}개 티켓에서 {total_conversations}개 대화, {error_count}개 실패")
        return total_conversations
    
    async def collect_raw_knowledge_base(self, progress: Dict, max_articles: Optional[int] = None) -> int:
        """
        지식베이스를 raw 데이터로 수집하여 저장
        기존 OptimizedFreshdeskFetcher.collect_raw_knowledge_base를 어댑터 패턴으로 수정
        """
        logger.info("지식베이스 raw 데이터 수집 시작" + (f" (최대 {max_articles}개)" if max_articles else ""))
        
        # 디렉토리 생성 및 초기 파일 준비
        target_dir = self.raw_data_dir / "knowledge_base"
        target_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"지식베이스 저장 디렉토리 준비 완료: {target_dir}")
        
        try:
            # 이미 수집된 지식베이스가 있는지 확인
            kb_chunks = progress.get("raw_data_progress", {}).get("knowledge_base_chunks", [])
            if kb_chunks:
                logger.info(f"이미 수집된 지식베이스 청크가 있습니다: {len(kb_chunks)}개")
                if max_articles:
                    logger.info("테스트 모드: 새로 수집을 시작합니다")
                    kb_chunks = []  # 테스트 모드에서는 기존 데이터 무시
                else:
                    logger.info("기존 수집 데이터를 유지합니다")
                    # 기존에 수집된 문서 수를 계산하여 반환
                    existing_articles_count = progress.get("raw_data_progress", {}).get("kb_articles_collected", 0)
                    logger.info(f"기존 수집된 지식베이스 문서 수: {existing_articles_count}개")
                    return existing_articles_count
            
            # 어댑터를 통해 지식베이스 수집 (정규화 적용됨)
            articles = await self.adapter.fetch_knowledge_base(max_articles=max_articles)
            
            if not articles:
                logger.warning("수집된 지식베이스 문서가 없습니다")
                return 0
            
            logger.info(f"수집된 지식베이스 문서 {len(articles)}개를 청크로 저장합니다")
            chunk_counter = len(kb_chunks)
            
            # 청크 단위로 저장
            for i in range(0, len(articles), self.KB_CHUNK_SIZE):
                chunk = articles[i:i + self.KB_CHUNK_SIZE]
                chunk_id = f"{chunk_counter:04d}"
                await self.save_raw_data_chunk(chunk, "knowledge_base", chunk_id)
                progress.setdefault("raw_data_progress", {}).setdefault("knowledge_base_chunks", []).append(chunk_id)
                chunk_counter += 1
                
                logger.info(f"지식베이스 청크 {chunk_id} 저장 완료: {len(chunk)}개 문서")
            
            # 지식베이스 수집 완료 시간 기록
            progress.setdefault("raw_data_progress", {})["last_kb_update"] = datetime.now().isoformat()
            progress.setdefault("raw_data_progress", {})["kb_articles_collected"] = len(articles)
            self.save_progress(progress)
            
            logger.info(f"지식베이스 raw 데이터 수집 완료: 총 {len(articles)}개 문서 (청크 {chunk_counter}개)")
            return len(articles)
            
        except Exception as e:
            logger.error(f"지식베이스 raw 데이터 수집 중 오류 발생: {e}")
            raise
    
    async def collect_raw_attachments(self, ticket_ids: List[str], progress: Dict) -> int:
        """
        티켓 첨부파일을 raw 데이터로 수집하여 저장
        기존 OptimizedFreshdeskFetcher.collect_raw_attachments를 어댑터 패턴으로 수정
        """
        logger.info(f"티켓 첨부파일 raw 데이터 수집 시작: {len(ticket_ids)}개 티켓")
        
        # 디렉토리 생성 및 초기 파일 준비
        target_dir = self.raw_data_dir / "attachments"
        target_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"첨부파일 저장 디렉토리 준비 완료: {target_dir}")
        
        try:
            # 이미 수집된 첨부파일 청크가 있는지 확인
            attachment_chunks = progress.get("raw_data_progress", {}).get("attachments_chunks", [])
            if attachment_chunks:
                logger.info(f"이미 수집된 첨부파일 청크가 있습니다: {len(attachment_chunks)}개")
                logger.info("기존 수집 데이터를 유지하고 새로운 데이터를 추가합니다")
            
            chunk_counter = len(attachment_chunks)
            current_chunk = []
            processed_tickets_count = 0  # 실제 첨부파일이 수집된 티켓 수를 추적
            
            for ticket_id in ticket_ids:
                try:
                    # 어댑터를 통해 첨부파일 정보 수집 (정규화 적용됨)
                    attachments_data = await self.adapter.fetch_attachments(ticket_id)
                    
                    if attachments_data:
                        # 티켓 ID와 함께 첨부파일 데이터 저장
                        ticket_attachment_data = {
                            "platform": self.platform,
                            "company_id": self.company_id,
                            "ticket_id": ticket_id,
                            "attachments": attachments_data,
                            "collected_at": datetime.now().isoformat()
                        }
                        current_chunk.append(ticket_attachment_data)
                        processed_tickets_count += 1  # 첨부파일이 있는 티켓만 카운트
                        
                        # 청크 크기 도달 시 저장
                        if len(current_chunk) >= self.RAW_DATA_CHUNK_SIZE:
                            chunk_id = f"{chunk_counter:04d}"
                            await self.save_raw_data_chunk(current_chunk, "attachments", chunk_id)
                            progress.setdefault("raw_data_progress", {}).setdefault("attachments_chunks", []).append(chunk_id)
                            
                            logger.info(f"첨부파일 청크 {chunk_id} 저장 완료: {len(current_chunk)}개 티켓")
                            current_chunk = []
                            chunk_counter += 1
                            
                            # 진행 상황 저장
                            self.save_progress(progress)
                    
                    # API 호출 간격 조절
                    await asyncio.sleep(self.REQUEST_DELAY)
                    
                except Exception as e:
                    logger.error(f"티켓 {ticket_id} 첨부파일 수집 오류: {e}")
                    continue
            
            # 마지막 청크 저장
            if current_chunk:
                chunk_id = f"{chunk_counter:04d}"
                await self.save_raw_data_chunk(current_chunk, "attachments", chunk_id)
                progress.setdefault("raw_data_progress", {}).setdefault("attachments_chunks", []).append(chunk_id)
                
                logger.info(f"첨부파일 마지막 청크 {chunk_id} 저장 완료: {len(current_chunk)}개 티켓")
            
            # 첨부파일 수집 완료 시간 기록
            progress.setdefault("raw_data_progress", {})["last_attachments_update"] = datetime.now().isoformat()
            progress.setdefault("raw_data_progress", {})["attachments_tickets_processed"] = len(ticket_ids)
            self.save_progress(progress)
            
            logger.info(f"티켓 첨부파일 raw 데이터 수집 완료: {processed_tickets_count}개 티켓에서 첨부파일 발견")
            return processed_tickets_count  # 실제 첨부파일이 수집된 티켓 수 반환
            
        except Exception as e:
            logger.error(f"첨부파일 raw 데이터 수집 중 오류 발생: {e}")
            raise
    
    # ========== 기존 OptimizedFreshdeskFetcher의 메인 수집 로직을 어댑터 패턴으로 리팩토링 ==========
    
    async def fetch_tickets_by_date_range(
        self, 
        start_date: str, 
        end_date: str,
        include_conversations: bool = True,
        include_attachments: bool = True,
        max_tickets: Optional[int] = None,
        current_total: int = 0
    ) -> List[Dict]:
        """
        특정 날짜 범위의 티켓을 수집
        기존 OptimizedFreshdeskFetcher.fetch_tickets_by_date_range를 어댑터 패턴으로 수정
        """
        tickets = []
        page = 1
        
        logger.info(f"날짜 범위 {start_date} ~ {end_date} 수집 시작")
        
        # 현재까지 수집한 전체 티켓 수 계산
        remaining_tickets = None
        if max_tickets is not None:
            remaining_tickets = max_tickets - current_total
            if remaining_tickets <= 0:
                logger.info(f"이미 최대 티켓 수({max_tickets})에 도달하여 수집 중단")
                return []
            logger.info(f"이 범위에서 수집 가능한 최대 티켓 수: {remaining_tickets}개")
        
        while True:
            # 최대 티켓 수에 도달했는지 확인
            if remaining_tickets is not None and len(tickets) >= remaining_tickets:
                logger.info(f"최대 티켓 수({max_tickets})에 도달하여 더 이상 수집하지 않음")
                break
            
            try:
                # 어댑터를 통해 티켓 목록 조회 (정규화 적용됨)
                batch_tickets = await self.adapter.fetch_tickets_by_date_range(
                    start_date, end_date, page, self.PER_PAGE
                )
                
                if not batch_tickets:
                    break
                
                # 최대 티켓 수 제한 적용
                if remaining_tickets is not None and len(tickets) + len(batch_tickets) > remaining_tickets:
                    batch_tickets = batch_tickets[:remaining_tickets - len(tickets)]
                    logger.info(f"남은 개수 제한으로 {len(batch_tickets)}개만 사용")
                
                # 추가 정보 수집
                if include_conversations or include_attachments:
                    batch_tickets = await self.enrich_tickets(
                        batch_tickets, include_conversations, include_attachments
                    )
                
                tickets.extend(batch_tickets)
                
                if len(batch_tickets) < self.PER_PAGE or (remaining_tickets is not None and len(tickets) >= remaining_tickets):
                    break
                    
                page += 1
                await asyncio.sleep(self.REQUEST_DELAY)
                
                logger.info(f"페이지 {page-1} 완료: {len(batch_tickets)}개 티켓 (현재까지 총 {len(tickets)}개)")
                
            except Exception as e:
                logger.error(f"페이지 {page} 수집 오류: {e}")
                break
                
        logger.info(f"날짜 범위 {start_date} ~ {end_date} 완료: 총 {len(tickets)}개")
        return tickets
    
    async def enrich_tickets(
        self, 
        tickets: List[Dict], 
        include_conversations: bool, 
        include_attachments: bool
    ) -> List[Dict]:
        """
        티켓에 대화내역, 첨부파일 등 추가 정보 수집
        어댑터 패턴을 사용하여 플랫폼별 구현 통일
        """
        enriched_tickets = []
        for ticket in tickets:
            ticket_id = ticket.get("id")
            try:
                if include_conversations:
                    # 이미 정규화된 구조에서 conversations 확인
                    if not ticket.get("conversations"):
                        conversations = await self.adapter.fetch_conversations(ticket_id)
                        ticket["conversations"] = conversations
                
                if include_attachments:
                    # 이미 정규화된 구조에서 attachments 확인  
                    if not ticket.get("attachments"):
                        attachments = await self.adapter.fetch_attachments(ticket_id)
                        ticket["attachments"] = attachments
                
                enriched_tickets.append(ticket)
            except Exception as e:
                logger.error(f"티켓 {ticket_id} 추가 정보 수집 오류: {e}")
                enriched_tickets.append(ticket)
        return enriched_tickets


# ========== 기존 OptimizedFreshdeskFetcher의 유틸리티 함수들 멀티플랫폼 버전으로 변환 ==========

async def collect_only_raw_data():
    """
    RAW 데이터만 수집하는 함수
    기존 optimized_fetcher.py의 collect_only_raw_data를 멀티플랫폼 버전으로 수정
    """
    logging.info("======= 멀티플랫폼 RAW 데이터 수집 시작 =======")
    
    # 환경변수에서 플랫폼 설정 로드 (기본값: Freshdesk)
    platform = os.getenv("PLATFORM", "freshdesk")
    company_id = os.getenv("COMPANY_ID")
    domain = os.getenv("FRESHDESK_DOMAIN") if platform == "freshdesk" else os.getenv(f"{platform.upper()}_DOMAIN")
    api_key = os.getenv("FRESHDESK_API_KEY") if platform == "freshdesk" else os.getenv(f"{platform.upper()}_API_KEY")
    
    if not all([company_id, domain, api_key]):
        # Freshdesk의 경우 도메인에서 company_id 추출 시도
        if platform == "freshdesk" and domain and api_key:
            from .freshdesk_adapter import FreshdeskAdapter
            # company_id 자동 추출 로직 (기존 optimized_fetcher.py와 동일)
            if ".freshdesk.com" in domain:
                company_id = domain.replace(".freshdesk.com", "")
            else:
                company_id = domain
            
            if company_id.startswith(("https://", "http://")):
                from urllib.parse import urlparse
                parsed_url = urlparse(company_id)
                company_id = parsed_url.netloc.replace(".freshdesk.com", "")
        else:
            logger.error(f"필수 환경변수가 설정되지 않았습니다: COMPANY_ID, {platform.upper()}_DOMAIN, {platform.upper()}_API_KEY")
            return
    
    config = {
        "platform": platform,
        "company_id": company_id,
        "domain": domain,
        "api_key": api_key,
        # 기존 OptimizedFreshdeskFetcher의 기본값들 재사용
        "max_retries": 5,
        "retry_delay": 2,
        "request_delay": 0.3,
        "per_page": 100,
        "chunk_size": 10000,
        "save_interval": 1000,
        "raw_data_chunk_size": 1000,
        "kb_chunk_size": 500
    }
    
    output_dir = "multi_platform_data"
    
    async with MultiPlatformDataCollector(config, output_dir) as collector:
        progress = collector.load_progress()
        
        ticket_ids = []
        chunks_completed = progress.get("chunks_completed", [])
        
        if not chunks_completed:
            logger.error("기존 티켓 데이터가 없습니다. 먼저 티켓 기본정보를 수집하세요.")
            return
        
        logger.info(f"기존 {len(chunks_completed)}개 청크에서 티켓 ID 추출 중...")
        
        for chunk_id in chunks_completed:
            # 플랫폼별 파일명 패턴으로 청크 파일 찾기
            chunk_file = collector.raw_data_dir / "tickets" / f"{platform}_tickets_chunk_{chunk_id}.json"
            if chunk_file.exists():
                try:
                    with open(chunk_file, 'r', encoding='utf-8') as f:
                        tickets = json.load(f)
                        chunk_ticket_ids = [str(t.get("id")) for t in tickets if t.get("id")]
                        ticket_ids.extend(chunk_ticket_ids)
                        logger.info(f"청크 {chunk_id}에서 {len(chunk_ticket_ids)}개 티켓 ID 추출")
                except Exception as e:
                    logger.error(f"청크 {chunk_id} 읽기 실패: {e}")
            else:
                logger.warning(f"청크 파일을 찾을 수 없음: {chunk_file}")
        
        logger.info(f"총 {len(ticket_ids)}개 티켓 ID 추출 완료")
        
        if ticket_ids:
            # 티켓 상세정보 수집
            await collector.collect_raw_ticket_details(ticket_ids, progress)
            
            # 대화내역 수집
            await collector.collect_raw_conversations(ticket_ids, progress)
            
            # 지식베이스 수집 (max_articles=None으로 전달하여 모든 문서 수집)
            await collector.collect_raw_knowledge_base(progress, max_articles=None)
            
            logger.info("RAW 데이터 수집 완료")
        else:
            logger.error("추출된 티켓 ID가 없습니다.")
    
    logging.info("======= 멀티플랫폼 RAW 데이터 수집 완료 =======")


if __name__ == "__main__":
    import sys
    
    # 명령행 인수 처리
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "raw":
            # RAW 데이터만 수집
            print("멀티플랫폼 RAW 데이터 수집을 시작합니다...")
            asyncio.run(collect_only_raw_data())
        
        else:
            print("사용법:")
            print("  python multi_platform_collector.py raw      # RAW 데이터만 수집")
    else:
        # 기본 동작: RAW 데이터 수집
        print("기본 모드: 멀티플랫폼 RAW 데이터 수집을 시작합니다...")
        asyncio.run(collect_only_raw_data())
