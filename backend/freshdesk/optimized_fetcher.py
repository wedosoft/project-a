"""
최적화된 Freshdesk 대용량 데이터 수집기

무제한 티켓 데이터를 효율적으로 수집하기 위한 최적화된 접근법
티켓 상세정보와 지식베이스 데이터를 포함한 완전한 raw 데이터 저장 지원
"""
import asyncio
import json
import logging
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from turtle import Turtle
from typing import Dict, List, Optional

import httpx
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 공통 로깅 모듈 사용 (core/logger.py)
from core.logger import get_logger

logger = get_logger(__name__)

FRESHDESK_DOMAIN = os.getenv("FRESHDESK_DOMAIN")
FRESHDESK_API_KEY = os.getenv("FRESHDESK_API_KEY")

if not FRESHDESK_DOMAIN or not FRESHDESK_API_KEY:
    raise RuntimeError("FRESHDESK_DOMAIN, FRESHDESK_API_KEY 환경 변수가 필요합니다.")

def extract_company_id_from_domain(domain: str) -> str:
    """
    FRESHDESK_DOMAIN에서 company_id를 추출합니다.
    
    Args:
        domain: Freshdesk 도메인 (예: "your-company.freshdesk.com" 또는 "your-company")
        
    Returns:
        str: 추출된 company_id
    """
    if not domain:
        raise ValueError("도메인이 비어있습니다.")
    
    # .freshdesk.com이 포함된 경우 제거
    if ".freshdesk.com" in domain:
        company_id = domain.replace(".freshdesk.com", "")
    else:
        company_id = domain
    
    # https:// 또는 http://가 포함된 경우 제거
    if company_id.startswith(("https://", "http://")):
        from urllib.parse import urlparse
        parsed_url = urlparse(company_id)
        company_id = parsed_url.netloc.replace(".freshdesk.com", "")
    
    return company_id

# company_id 자동 추출
COMPANY_ID = extract_company_id_from_domain(FRESHDESK_DOMAIN)
logger.info(f"FRESHDESK_DOMAIN '{FRESHDESK_DOMAIN}'에서 추출된 company_id: '{COMPANY_ID}'")

BASE_URL = f"https://{FRESHDESK_DOMAIN}" if ".freshdesk.com" in FRESHDESK_DOMAIN else f"https://{FRESHDESK_DOMAIN}.freshdesk.com"
BASE_URL += "/api/v2"

# X-Company-ID 헤더를 포함한 기본 헤더 설정
HEADERS = {
    "Content-Type": "application/json",
    "X-Company-ID": COMPANY_ID
}
AUTH = (FRESHDESK_API_KEY, "X")

# 최적화된 설정
MAX_RETRIES = 5
RETRY_DELAY = 2
PER_PAGE = 100  # 최대값 사용
REQUEST_DELAY = 0.3  # Enterprise 기준 200req/min → 300ms 간격

# 청크 기반 처리 설정
CHUNK_SIZE = 10000  # 청크당 티켓 수
SAVE_INTERVAL = 1000  # 1000개마다 중간 저장

# RAW 데이터 저장 설정
RAW_DATA_CHUNK_SIZE = 1000  # raw 데이터 청크당 항목 수
KB_CHUNK_SIZE = 500  # 지식베이스 청크당 항목 수


class OptimizedFreshdeskFetcher:
    """
    대용량 티켓 데이터 수집을 위한 최적화된 클래스
    티켓 상세정보와 지식베이스를 raw 데이터로 저장하여 임베딩 실패 시 재수집 방지
    """
    
    def __init__(self, output_dir: str = "freshdesk_full_data"):
        # output_dir이 절대경로가 아니면 backend/ 기준으로 보정
        output_path = Path(output_dir)
        if not output_path.is_absolute():
            # backend/ 하위로 강제
            backend_root = Path(__file__).parent.parent
            output_path = backend_root / output_path
        self.output_dir = output_path.resolve()
        self.output_dir.mkdir(exist_ok=True)
        
        # 하위 디렉토리 생성 (raw 데이터 저장용)
        self.raw_data_dir = self.output_dir / "raw_data"
        self.raw_data_dir.mkdir(exist_ok=True)
        
        # 세부 raw 데이터 디렉토리 생성
        (self.raw_data_dir / "tickets").mkdir(exist_ok=True)
        (self.raw_data_dir / "ticket_details").mkdir(exist_ok=True)
        (self.raw_data_dir / "conversations").mkdir(exist_ok=True)
        (self.raw_data_dir / "attachments").mkdir(exist_ok=True)
        (self.raw_data_dir / "knowledge_base").mkdir(exist_ok=True)
        
        self.progress_file = self.output_dir / "progress.json"
        self.client = None
        
        # 설정값 인스턴스 변수 초기화 (large_scale_config.py 연동 용이하게)
        self.MAX_RETRIES = MAX_RETRIES
        self.RETRY_DELAY = RETRY_DELAY
        self.PER_PAGE = PER_PAGE
        self.REQUEST_DELAY = REQUEST_DELAY
        self.CHUNK_SIZE = CHUNK_SIZE
        self.SAVE_INTERVAL = SAVE_INTERVAL
        self.RAW_DATA_CHUNK_SIZE = RAW_DATA_CHUNK_SIZE
        self.KB_CHUNK_SIZE = KB_CHUNK_SIZE
        
    async def __aenter__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()

    def save_progress(self, progress_data: Dict):
        """진행 상황을 파일에 저장"""
        # 타임스탬프 추가로 최종 업데이트 시간 기록
        progress_data["last_updated_timestamp"] = datetime.now().isoformat()
        with open(self.progress_file, 'w') as f:
            json.dump(progress_data, f, indent=2)
            
    def load_progress(self) -> Dict:
        """저장된 진행 상황 로드"""
        if self.progress_file.exists():
            with open(self.progress_file, 'r') as f:
                progress = json.load(f)
                logger.info(f"기존 진행 상황 로드: {progress.get('total_collected', 0):,}개 티켓, {len(progress.get('completed_ranges', []))}개 날짜 범위 완료")
                return progress
        # 기본 진행 정보 생성
        return {
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

    async def fetch_with_retry(self, url: str, params: Optional[Dict] = None) -> Dict:
        """재시도 로직이 포함된 API 호출"""
        retries = 0
        while retries < self.MAX_RETRIES:
            try:
                resp = await self.client.get(url, headers=HEADERS, auth=AUTH, params=params)
                
                # Rate limit 체크 (명시적인 429 상태 코드)
                if resp.status_code == 429:
                    retry_after = int(resp.headers.get('Retry-After', 60))
                    logger.warning(f"Rate limit 도달. {retry_after}초 대기 중...")
                    await asyncio.sleep(retry_after)
                    retries += 1
                    continue
                
                # 헤더에서 API 호출 제한 정보 확인
                remaining = resp.headers.get('X-RateLimit-Remaining')
                if remaining and int(remaining) <= 1:  # 남은 요청이 1개 이하면 잠시 대기
                    wait_time = 5  # 기본 5초 대기
                    reset_time = resp.headers.get('X-RateLimit-Reset')
                    if reset_time:
                        # Unix timestamp에서 현재 시간을 빼서 남은 시간 계산
                        import time
                        now = int(time.time())
                        reset = int(reset_time)
                        wait_time = max(reset - now, 1)  # 최소 1초
                    
                    logger.info(f"API 제한에 도달하여 {wait_time}초 대기 중 (남은 요청: {remaining})")
                    await asyncio.sleep(wait_time)
                    
                resp.raise_for_status()
                return resp.json()
                
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP 오류 {e.response.status_code}: {e}")
                if e.response.status_code in [500, 502, 503, 504]:
                    retries += 1
                    wait_time = self.RETRY_DELAY * (2 ** retries)
                    logger.info(f"{wait_time}초 대기 후 재시도 ({retries}/{self.MAX_RETRIES})...")
                    await asyncio.sleep(wait_time)
                else:
                    raise
                    
            except Exception as e:
                logger.error(f"요청 오류: {e}")
                retries += 1
                if retries < self.MAX_RETRIES:
                    wait_time = self.RETRY_DELAY * (2 ** retries)
                    logger.info(f"요청 오류 발생 후 {wait_time}초 대기 후 재시도 ({retries}/{self.MAX_RETRIES})...")
                    await asyncio.sleep(wait_time)
                else:
                    raise
        
        # 최대 재시도 횟수 초과
        raise Exception(f"최대 재시도 횟수({self.MAX_RETRIES})에 도달했습니다: {url}")

    def get_date_ranges(self, start_date: Optional[str] = None, end_date: Optional[str] = None, days_per_chunk: int = 30) -> List[tuple]:
        """
        날짜 범위를 분할하여 반환
        
        Args:
            start_date: 시작 날짜 (YYYY-MM-DD), None이면 현재부터 10년 전
            end_date: 종료 날짜 (YYYY-MM-DD), 없으면 현재 날짜
            days_per_chunk: 청크당 일수 (기본 30일, 대용량 티켓 수집 시 7-14일 권장)
        
        Returns:
            List[tuple]: (시작날짜, 종료날짜) 튜플 목록
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

    async def fetch_ticket_detail_raw(self, ticket_id: str) -> Optional[Dict]:
        """
        티켓 상세정보를 raw 형태로 수집
        
        Args:
            ticket_id: 티켓 ID
            
        Returns:
            Dict: 티켓 상세정보 또는 None (실패 시)
        """
        try:
            detail = await self.fetch_with_retry(f"{BASE_URL}/tickets/{ticket_id}")
            await asyncio.sleep(self.REQUEST_DELAY)
            return detail
        except Exception as e:
            logger.error(f"티켓 {ticket_id} 상세정보 수집 실패: {e}")
            return None
    
    async def fetch_conversations_raw(self, ticket_id: str) -> List[Dict]:
        """
        티켓 대화내역을 raw 형태로 수집
        
        Args:
            ticket_id: 티켓 ID
            
        Returns:
            List[Dict]: 대화내역 목록
        """
        try:
            conversations = await self.fetch_with_retry(f"{BASE_URL}/tickets/{ticket_id}/conversations")
            await asyncio.sleep(self.REQUEST_DELAY)
            # API 응답이 dict인 경우 빈 리스트 반환, list인 경우 그대로 반환
            if isinstance(conversations, dict):
                return []
            return conversations if conversations else []
        except Exception as e:
            logger.error(f"티켓 {ticket_id} 대화내역 수집 실패: {e}")
            return []
    
    async def fetch_attachments_raw(self, ticket_id: str) -> List[Dict]:
        """
        티켓 첨부파일 정보를 raw 형태로 수집
        
        Args:
            ticket_id: 티켓 ID
            
        Returns:
            List[Dict]: 첨부파일 정보 목록
        """
        try:
            # Freshdesk API에서 첨부파일은 보통 티켓 상세정보에 포함되어 있음
            # 별도 엔드포인트가 없으므로 티켓 상세에서 추출
            detail = await self.fetch_ticket_detail_raw(ticket_id)
            if detail and 'attachments' in detail:
                return detail['attachments']
            return []
        except Exception as e:
            logger.error(f"티켓 {ticket_id} 첨부파일 정보 수집 실패: {e}")
            return []
    
    async def fetch_knowledge_base_raw(self, category_id: Optional[str] = None, max_articles: Optional[int] = None) -> List[Dict]:
        """
        지식베이스 문서 수집 (raw 데이터 형태)
        Freshdesk API 문서에 맞게 카테고리 → 폴더 → 아티클 계층 구조로 접근
        
        Args:
            category_id: 특정 카테고리 ID (None이면 전체)
            max_articles: 최대 수집 항목 수 (None이면 제한 없음)
            
        Returns:
            List[Dict]: 지식베이스 항목 목록
        """
        all_articles = []
        articles_count = 0
        
        try:
            logger.info("지식베이스 수집 시작" + (f" (최대 {max_articles}개)" if max_articles else ""))
            
            # 1. 카테고리 목록 가져오기
            categories = []
            if category_id:
                # 특정 카테고리만 조회
                category = await self.fetch_with_retry(f"{BASE_URL}/solutions/categories/{category_id}")
                if category:
                    categories = [category]
            else:
                # 전체 카테고리 조회
                categories = await self.fetch_with_retry(f"{BASE_URL}/solutions/categories")
            
            logger.info(f"카테고리 {len(categories)}개 수신 완료")
            
            # 2. 각 카테고리별 폴더 및 아티클 수집
            for category in categories:
                cat_id = category["id"]
                cat_name = category.get("name", "Unknown")
                logger.info(f"카테고리 '{cat_name}' (ID: {cat_id}) 처리 중...")
                
                # 폴더 목록 가져오기
                folders = await self.fetch_with_retry(f"{BASE_URL}/solutions/categories/{cat_id}/folders")
                logger.info(f"카테고리 '{cat_name}'에서 폴더 {len(folders)}개 수신 완료")
                
                # 3. 각 폴더별 아티클 수집
                for folder in folders:
                    folder_id = folder["id"]
                    folder_name = folder.get("name", "Unknown")
                    logger.info(f"폴더 '{folder_name}' (ID: {folder_id}) 처리 중...")
                    
                    # 폴더별 페이지네이션 처리
                    page = 1
                    while True:
                        params = {
                            "page": page,
                            "per_page": self.PER_PAGE
                        }
                        
                        logger.info(f"폴더 '{folder_name}'의 아티클 페이지 {page} 요청 중...")
                        folder_articles = await self.fetch_with_retry(
                            f"{BASE_URL}/solutions/folders/{folder_id}/articles", 
                            params
                        )
                        
                        if not folder_articles:
                            logger.info(f"폴더 '{folder_name}'에 더 이상 아티클이 없습니다")
                            break
                        
                        # 카테고리 및 폴더 정보 추가
                        for article in folder_articles:
                            article["category_id"] = cat_id
                            article["category_name"] = cat_name
                            article["folder_id"] = folder_id
                            article["folder_name"] = folder_name
                        
                        # 최대 항목 수 제한이 있을 경우
                        if max_articles is not None:
                            remaining = max_articles - articles_count
                            if remaining <= 0:
                                logger.info(f"최대 수집 개수({max_articles})에 도달하여 중단")
                                break
                                
                            if len(folder_articles) > remaining:
                                folder_articles = folder_articles[:remaining]
                            
                            all_articles.extend(folder_articles)
                            articles_count += len(folder_articles)
                            logger.info(f"아티클 {len(folder_articles)}개 추가 (현재까지 총 {articles_count}/{max_articles}개)")
                            
                            if articles_count >= max_articles:
                                break
                        else:
                            all_articles.extend(folder_articles)
                            articles_count += len(folder_articles)
                            logger.info(f"아티클 {len(folder_articles)}개 추가 (현재까지 총 {articles_count}개)")
                        
                        # 이 배치가 불완전하면 마지막 페이지
                        if len(folder_articles) < self.PER_PAGE:
                            break
                            
                        page += 1
                        await asyncio.sleep(self.REQUEST_DELAY)
                    
                    # 최대 항목 수에 도달했으면 중단
                    if max_articles is not None and articles_count >= max_articles:
                        logger.info(f"최대 수집 개수({max_articles})에 도달하여 중단")
                        break
                
                # 최대 항목 수에 도달했으면 중단
                if max_articles is not None and articles_count >= max_articles:
                    break
            
            logger.info(f"지식베이스 수집 완료: 총 {len(all_articles)}개 아티클")
            return all_articles
            
        except Exception as e:
            logger.error(f"지식베이스 수집 실패: {e}")
            raise

    async def save_raw_data_chunk(self, data: List[Dict], data_type: str, chunk_id: str) -> None:
        """
        Raw 데이터를 청크 단위로 저장합니다.
        
        Args:
            data: 저장할 데이터 리스트
            data_type: 데이터 유형 (ticket_details, conversations, knowledge_base, attachments)
            chunk_id: 청크 ID (문자열, 예: "0000")
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
        
        # 파일 경로 생성
        chunk_file = data_type_dir / f"{data_type}_chunk_{chunk_id}.json"
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
    
    
    async def collect_raw_ticket_details(self, ticket_ids: List[str], progress: Dict) -> int:
        """
        티켓 상세정보를 raw 형태로 수집하여 저장합니다.
        
        Args:
            ticket_ids: 상세정보를 수집할 티켓 ID 리스트
            progress: 진행 상황 딕셔너리
            
        Returns:
            int: 성공적으로 수집된 티켓 수
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
        logger.info(f"🔍 [DEBUG] 티켓 상세정보 저장 디렉토리 생성 완료: {target_dir.exists()}")
        
        chunk_counter = len(progress.get("raw_data_progress", {}).get("ticket_details_chunks", []))
        current_chunk = []
        success_count = 0
        error_count = 0
        logger.info(f"🔍 [DEBUG] 초기값 - chunk_counter: {chunk_counter}, current_chunk 크기: {len(current_chunk)}")
        
        for i, ticket_id in enumerate(ticket_ids):
            try:
                detail = await self.fetch_ticket_detail_raw(str(ticket_id))
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
                logger.info(f"🔍 [DEBUG] save_raw_data_chunk 호출 - chunk_id: {chunk_id}, 데이터 수: {len(current_chunk)}")
                await self.save_raw_data_chunk(current_chunk, "ticket_details", chunk_id)
                progress.setdefault("raw_data_progress", {}).setdefault("ticket_details_chunks", []).append(chunk_id)
                chunk_counter += 1
                current_chunk = []
                logger.info(f"🔍 [DEBUG] 청크 저장 완료 - 다음 chunk_counter: {chunk_counter}")
                
                # 진행 상황 저장
                self.save_progress(progress)
            
            if (i + 1) % 100 == 0:
                logger.info(f"티켓 상세정보 수집 진행률: {i+1}/{len(ticket_ids)} (성공: {success_count}, 실패: {error_count})")
        
        # 마지막 청크 저장
        if current_chunk:
            chunk_id = f"{chunk_counter:04d}"
            logger.info(f"티켓 상세정보 마지막 청크 {chunk_id} 저장 중: {len(current_chunk)}개 항목")
            logger.info(f"🔍 [DEBUG] 마지막 청크 save_raw_data_chunk 호출 - chunk_id: {chunk_id}, 데이터 수: {len(current_chunk)}")
            await self.save_raw_data_chunk(current_chunk, "ticket_details", chunk_id)
            progress.setdefault("raw_data_progress", {}).setdefault("ticket_details_chunks", []).append(chunk_id)
            logger.info(f"🔍 [DEBUG] 마지막 청크 저장 완료")
        
        logger.info(f"티켓 상세정보 수집 완료: {success_count}개 성공, {error_count}개 실패")
        logger.info(f"🔍 [DEBUG] collect_raw_ticket_details 완료 - 총 성공: {success_count}, 총 실패: {error_count}")
        return success_count

    async def collect_raw_conversations(self, ticket_ids: List[str], progress: Dict) -> int:
        """
        티켓 대화내역을 raw 데이터로 수집하여 저장
        
        Args:
            ticket_ids: 수집할 티켓 ID 목록
            progress: 진행 상황 딕셔너리
            
        Returns:
            int: 실제로 수집된 대화내역 총 수
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
                conversations = await self.fetch_conversations_raw(str(ticket_id))
                if conversations:
                    # 각 대화에 ticket_id 추가하여 나중에 연결 가능하도록 함
                    for conv in conversations:
                        conv["ticket_id"] = ticket_id
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
        
        # 실제 수집된 대화내역 총 수 반환
        return total_conversations
    
    async def collect_raw_knowledge_base(self, progress: Dict, max_articles: Optional[int] = None) -> int:
        """
        지식베이스를 raw 데이터로 수집하여 저장
        
        Args:
            progress: 진행 상황 딕셔너리
            max_articles: 최대 수집 항목 수 (None이면 제한 없음)
            
        Returns:
            int: 실제 수집된 지식베이스 문서 수
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
            
            articles = await self.fetch_knowledge_base_raw(max_articles=max_articles)
            
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
        
        Args:
            ticket_ids: 첨부파일을 수집할 티켓 ID 목록
            progress: 진행 상황 딕셔너리
            
        Returns:
            int: 실제 첨부파일이 수집된 티켓 수
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
                    # 개별 티켓의 첨부파일 정보 수집
                    attachments_data = await self.fetch_attachments_raw(ticket_id)
                    
                    if attachments_data:
                        # 티켓 ID와 함께 첨부파일 데이터 저장
                        ticket_attachment_data = {
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
            
        except Exception as e:
            logger.error(f"첨부파일 raw 데이터 수집 중 오류 발생: {e}")
            raise

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
        특정 날짜 범위의 티켓을 수집합니다.

        Args:
            start_date (str): 수집을 시작할 날짜 (YYYY-MM-DD 형식).
            end_date (str): 수집을 종료할 날짜 (YYYY-MM-DD 형식).
            include_conversations (bool): True로 설정하면 각 티켓의 대화내역을 포함하여 수집합니다.
            include_attachments (bool): True로 설정하면 각 티켓의 첨부파일 정보를 포함하여 수집합니다.
            max_tickets (Optional[int]): 수집할 티켓의 최대 개수 (None이면 제한 없음).
            current_total (int): 현재까지 수집된 티켓 수. max_tickets와 비교하여 남은 티켓 수를 계산합니다.

        Returns:
            List[Dict]: 수집된 티켓의 목록.
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
            
            params = {
                "page": page,
                "per_page": self.PER_PAGE,
                "updated_since": start_date,
                "order_by": "updated_at",
                "order_type": "asc"
            }
            
            # 종료 날짜 필터 추가 (Freshdesk는 updated_until 파라미터가 없으므로 클라이언트에서 필터링)
            
            try:
                batch_tickets = await self.fetch_with_retry(f"{BASE_URL}/tickets", params)
                
                if not batch_tickets:
                    break
                    
                # 종료 날짜 이후 티켓 필터링
                filtered_tickets = [
                    t for t in batch_tickets 
                    if t.get('updated_at', '') <= end_date
                ]
                
                # 모든 티켓이 종료 날짜 이내인 경우에만 계속 수집
                end_date_filter_active = len(batch_tickets) != len(filtered_tickets)
                
                # 최대 티켓 수 제한 적용
                if remaining_tickets is not None and len(tickets) + len(filtered_tickets) > remaining_tickets:
                    filtered_tickets = filtered_tickets[:remaining_tickets - len(tickets)]
                    logger.info(f"남은 개수 제한으로 {len(filtered_tickets)}개만 사용 (원래는 {len(batch_tickets)}개)")
                
                # 추가 정보 수집
                if include_conversations or include_attachments:
                    filtered_tickets = await self.enrich_tickets(
                        filtered_tickets, include_conversations, include_attachments
                    )
                
                tickets.extend(filtered_tickets)
                
                # 종료 날짜 필터가 활성화되고 필터링으로 일부 티켓이 제외된 경우
                # 즉, 이미 종료 날짜를 넘어선 티켓이 포함되어 있으면 중단
                if end_date_filter_active:
                    logger.info(f"날짜 범위 종료점 도달 (페이지 {page}, 필터링됨: {len(batch_tickets) - len(filtered_tickets)}개)")
                    break
                    
                if len(batch_tickets) < self.PER_PAGE or (remaining_tickets is not None and len(tickets) >= remaining_tickets):
                    break
                    
                page += 1
                await asyncio.sleep(self.REQUEST_DELAY)
                
                logger.info(f"페이지 {page-1} 완료: {len(filtered_tickets)}개 티켓 (현재까지 총 {len(tickets)}개)")
                
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
        """티켓에 대화내역, 첨부파일, description, description_text 등 모든 주요 필드 추가"""
        enriched_tickets = []
        for ticket in tickets:
            ticket_id = ticket.get("id")
            try:
                # description, description_text 등 주요 필드가 누락된 경우 상세 정보로 보완
                if not ticket.get("description") or not ticket.get("description_text") or (include_attachments and "attachments" not in ticket):
                    from .fetcher import fetch_ticket_details
                    detail = await fetch_ticket_details(ticket_id)
                    if detail:
                        ticket.update({
                            k: v for k, v in detail.items() if k not in ticket or not ticket[k]
                        })
                if include_conversations:
                    conversations = ticket.get("conversations")
                    if not conversations:
                        from .fetcher import fetch_ticket_conversations
                        conversations = await fetch_ticket_conversations(self.client, ticket_id)
                        ticket["conversations"] = conversations
                if include_attachments:
                    # 안전하게 attachments 접근 (None이거나 존재하지 않는 경우 방지)
                    attachments = ticket.get("attachments", []) or ticket.get("all_attachments", [])
                    if not attachments:
                        from .fetcher import fetch_ticket_attachments
                        attachments = await fetch_ticket_attachments(self.client, ticket_id)
                        # None이 아닌 경우에만 할당 (빈 리스트도 유효한 값으로 간주)
                        if attachments is not None:
                            ticket["attachments"] = attachments
                enriched_tickets.append(ticket)
            except Exception as e:
                logger.error(f"티켓 {ticket_id} 추가 정보 수집 오류: {e}")
                enriched_tickets.append(ticket)
        return enriched_tickets

    def save_tickets_chunk(self, tickets: List[Dict], chunk_id: str):
        """
        티켓 청크를 저장 - raw_data/tickets/ 디렉토리에만 저장
        크기 제한을 고려하여 청킹을 수행합니다.
        
        Args:
            tickets (List[Dict]): 저장할 티켓 데이터의 리스트. 각 티켓은 딕셔너리 형태로 제공됩니다.
            chunk_id (str): 저장할 청크의 고유 ID. 파일 이름에 사용됩니다.
        
        Raises:
            OSError: 파일 쓰기 중 문제가 발생한 경우.
            ValueError: tickets가 비어 있는 경우.
        """
        if not tickets:
            logger.warning(f"빈 티켓 리스트로 인해 청크 {chunk_id} 저장을 건너뜁니다.")
            return
            
        # raw_data/tickets/ 디렉토리에 청크 파일 저장
        tickets_dir = self.raw_data_dir / "tickets"
        tickets_dir.mkdir(parents=True, exist_ok=True)  # 디렉토리 생성 보장
        raw_chunk_file = tickets_dir / f"tickets_chunk_{chunk_id}.json"
        
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
            "chunk_id": chunk_id,
            "ticket_count": len(tickets),
            "file_size_mb": round(file_size_mb, 2),
            "file_path": str(raw_chunk_file)
        }, ensure_ascii=False))
        logger.info(f"  → 저장 경로: {raw_chunk_file} ({file_size_mb:.1f}MB)")

    async def collect_all_tickets(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        include_conversations: bool = False,
        include_attachments: bool = False,
        max_tickets: Optional[int] = None,
        max_kb_articles: Optional[int] = None,  # 지식베이스 최대 항목 수
        resource_check_func = None,
        resource_check_interval: int = 1000,
        days_per_chunk: int = 30,  # 날짜 범위 청크 크기 (일)
        adaptive_rate: bool = True,   # 적응형 속도 조절 활성화 여부
        collect_raw_details: bool = True,  # 티켓 상세정보 raw 데이터 수집 여부
        collect_raw_conversations: bool = True,  # 대화내역 raw 데이터 수집 여부
        collect_raw_attachments: bool = True,  # 첨부파일 raw 데이터 수집 여부
        collect_raw_kb: bool = True  # 지식베이스 raw 데이터 수집 여부
    ) -> Dict:
        """
        모든 티켓을 효율적으로 수집
        
        Args:
            start_date: 시작 날짜 (YYYY-MM-DD)
            end_date: 종료 날짜 (없으면 현재까지)
            include_conversations: 대화 내역 포함 여부 (기본 티켓 수집 시)
            include_attachments: 첨부파일 정보 포함 여부 (기본 티켓 수집 시)
            max_tickets: 최대 수집 티켓 수 (None=무제한)
            resource_check_func: 리소스 체크 함수 (None=체크 안함)
            resource_check_interval: 리소스 체크 간격 (티켓 수)
            days_per_chunk: 날짜 범위 분할 단위 (일)
            adaptive_rate: 서버 응답에 따른 요청 간격 자동 조절
            collect_raw_details: 티켓 상세정보 raw 데이터 수집 여부
            collect_raw_conversations: 대화내역 raw 데이터 수집 여부  
            collect_raw_attachments: 첨부파일 raw 데이터 수집 여부
            collect_raw_kb: 지식베이스 raw 데이터 수집 여부
            collect_raw_details: 티켓 상세정보를 raw 데이터로 수집할지 여부
            collect_raw_conversations: 대화내역을 raw 데이터로 수집할지 여부
            collect_raw_kb: 지식베이스를 raw 데이터로 수집할지 여부
            
        Returns:
            Dict: 수집 통계 정보
        """
        # start_date가 None이면 현재부터 10년 전으로 설정
        if start_date is None:
            ten_years_ago = datetime.now() - timedelta(days=365 * 10)
            start_date = ten_years_ago.strftime("%Y-%m-%d")
            logger.info(f"start_date가 지정되지 않아 기본값으로 10년 전 날짜를 사용합니다: {start_date}")
        
        progress = self.load_progress()
        date_ranges = self.get_date_ranges(start_date, end_date, days_per_chunk)
        
        total_tickets = progress.get("total_collected", 0)
        chunk_counter = len(progress.get("chunks_completed", []))
        current_chunk = []
        
        # 수집된 티켓 ID 목록 (raw 데이터 수집용)
        collected_ticket_ids = []
        
        # 이미 완료된 날짜 범위가 있으면 표시
        completed_ranges = progress.get("completed_ranges", [])
        if completed_ranges:
            logger.info(f"이미 {len(completed_ranges)}/{len(date_ranges)}개 날짜 범위가 처리되었습니다.")
        
        logger.info(f"총 {len(date_ranges)}개 날짜 범위로 분할하여 수집 시작")
        logger.info(f"날짜 범위 목록: {date_ranges[:5]}{'...' if len(date_ranges) > 5 else ''}")
        
        if max_tickets is not None:
            logger.info(f"최대 {max_tickets}개 티켓만 수집합니다")
        
        # Raw 데이터 수집 설정 로깅
        logger.info(f"Raw 데이터 수집 설정:")
        logger.info(f"  - 티켓 상세정보: {collect_raw_details}")
        logger.info(f"  - 대화내역: {collect_raw_conversations}")  
        logger.info(f"  - 지식베이스: {collect_raw_kb}")
        logger.info(f"  - 첨부파일: {collect_raw_attachments}")
        
        # 적응형 속도 조절 설정
        if adaptive_rate:
            original_request_delay = self.REQUEST_DELAY
            consecutive_429_count = 0  # 연속 429 오류 횟수 추적
        
        for i, (range_start, range_end) in enumerate(date_ranges):
            # 최대 티켓 수 제한이 있을 경우만 체크
            if max_tickets is not None and total_tickets >= max_tickets:
                logger.info(f"최대 티켓 수({max_tickets})에 도달, 수집 중단")
                break
                
            # 시스템 리소스 체크
            if resource_check_func and i % resource_check_interval == 0 and i > 0:
                if not resource_check_func():
                    logger.warning("시스템 리소스 부족으로 수집 일시 중단")
                    break
                
            # 이미 처리된 날짜 범위는 건너뛰기
            range_id = f"{range_start}_{range_end}"
            if range_id in completed_ranges:
                logger.info(f"날짜 범위 {i+1}/{len(date_ranges)}: {range_start} ~ {range_end} 이미 처리됨, 건너뜀")
                continue
            
            try:
                logger.info(f"날짜 범위 {i+1}/{len(date_ranges)} 처리 중: {range_start} ~ {range_end}")
                
                # 현재까지 수집된 티켓 수를 전달하여 페이지별로 제한 적용
                tickets = await self.fetch_tickets_by_date_range(
                    range_start, range_end, 
                    include_conversations, include_attachments,
                    max_tickets=max_tickets,  # 최대 티켓 수 전달
                    current_total=total_tickets  # 현재까지 수집된 티켓 수 전달
                )
                
                # 적응형 속도 조절
                if adaptive_rate:
                    if consecutive_429_count > 0:
                        # 정상 응답이 오면 연속 오류 카운터를 리셋
                        consecutive_429_count = 0
                        # 서서히 원래 속도로 복귀 (25% 감소씩)
                        self.REQUEST_DELAY = max(original_request_delay, self.REQUEST_DELAY * 0.75)
                        logger.info(f"요청 간격 조정: {self.REQUEST_DELAY:.2f}초")
                
                range_ticket_count = len(tickets)
                logger.info(f"날짜 범위 {range_start} ~ {range_end}에서 {range_ticket_count}개 티켓 수집됨")
                
                # 티켓 ID 수집 (raw 데이터 수집용)
                logger.debug(f"Raw 데이터 수집 설정 확인: collect_raw_details={collect_raw_details}, collect_raw_conversations={collect_raw_conversations}")
                logger.info(f"🔍 [DEBUG] 플래그 값 확인 - collect_raw_details: {collect_raw_details}, collect_raw_conversations: {collect_raw_conversations}")
                logger.info(f"🔍 [DEBUG] 조건 체크 결과: {collect_raw_details or collect_raw_conversations}")
                
                if collect_raw_details or collect_raw_conversations:
                    ticket_ids = [str(t.get("id")) for t in tickets if t.get("id")]
                    collected_ticket_ids.extend(ticket_ids)
                    logger.info(f"이 범위에서 수집된 티켓 ID {len(ticket_ids)}개: {ticket_ids[:5]}{'...' if len(ticket_ids) > 5 else ''}")
                    logger.info(f"총 누적 티켓 ID 수: {len(collected_ticket_ids)}")
                    logger.info(f"🔍 [DEBUG] 티켓 ID 수집 완료 - 이번 범위: {len(ticket_ids)}개, 총 누적: {len(collected_ticket_ids)}개")
                else:
                    logger.info("Raw 데이터 수집이 비활성화되어 티켓 ID를 수집하지 않습니다.")
                    logger.info(f"🔍 [DEBUG] Raw 데이터 수집 건너뜀 - 플래그 값: collect_raw_details={collect_raw_details}, collect_raw_conversations={collect_raw_conversations}")
                
                current_chunk.extend(tickets)
                total_tickets += range_ticket_count
                
                # max_tickets에 도달했으면 더 이상 수집하지 않음
                if max_tickets is not None and total_tickets >= max_tickets:
                    logger.info(f"최대 티켓 수({max_tickets})에 정확히 도달, 수집 완료")
                    
                    # 이 범위에서 일부만 사용한 경우 상세 정보 기록
                    range_details = {
                        "tickets_collected": range_ticket_count,
                        "partial": True,  # 부분적으로 수집됨
                        "completed_at": datetime.now().isoformat()
                    }
                    progress.setdefault("range_details", {})[range_id] = range_details
                    
                    # 완료된 범위 목록에 추가
                    if range_id not in completed_ranges:
                        progress.setdefault("completed_ranges", []).append(range_id)
                    
                    # 진행 상황 업데이트 후 종료
                    progress["total_collected"] = total_tickets
                    progress["last_updated"] = datetime.now().isoformat()
                    self.save_progress(progress)
                    break
                
                # 청크 크기에 도달하면 저장 (RAW_DATA_CHUNK_SIZE 사용으로 변경)
                if len(current_chunk) >= self.RAW_DATA_CHUNK_SIZE:
                    chunk_id = f"{chunk_counter:04d}"
                    self.save_tickets_chunk(current_chunk, chunk_id)
                    progress.setdefault("chunks_completed", []).append(chunk_id)
                    chunk_counter += 1
                    current_chunk = []
                    logger.info(f"티켓 청크 {chunk_id} 저장 완료: {self.RAW_DATA_CHUNK_SIZE}개 티켓")
                
                # 주기적 진행률 로깅 (1000개마다)
                if total_tickets % 1000 == 0 and total_tickets > 0:
                    logger.info(f"티켓 수집 진행률: {total_tickets}개 수집됨, 현재 청크 크기: {len(current_chunk)}개")
                
                # 이 날짜 범위의 상세 정보 기록
                range_details = {
                    "tickets_collected": range_ticket_count,
                    "partial": False,  # 전체 수집됨
                    "completed_at": datetime.now().isoformat()
                }
                progress.setdefault("range_details", {})[range_id] = range_details
                
                # 진행 상황 업데이트
                if range_id not in completed_ranges:
                    progress.setdefault("completed_ranges", []).append(range_id)
                progress["total_collected"] = total_tickets
                progress["last_updated"] = datetime.now().isoformat()
                self.save_progress(progress)
                
                logger.info(f"진행률: {i+1}/{len(date_ranges)} ({total_tickets:,}개 수집)")
                
            except httpx.HTTPStatusError as e:
                # HTTP 429 (Too Many Requests) 오류 처리
                if e.response.status_code == 429 and adaptive_rate:
                    consecutive_429_count += 1
                    # 429 오류가 연속으로 발생하면 요청 간격을 점진적으로 증가
                    self.REQUEST_DELAY *= (1.5 + (0.5 * consecutive_429_count))
                    logger.warning(f"Rate limit 도달로 요청 간격 증가: {self.REQUEST_DELAY:.2f}초")
                    
                    # 너무 빈번한 요청으로 잠시 대기 후 다음 범위 시도
                    retry_after = int(e.response.headers.get('Retry-After', 60))
                    logger.warning(f"{retry_after}초 대기 후 다음 날짜 범위 시도...")
                    await asyncio.sleep(retry_after)
                    continue
                    
                logger.error(f"날짜 범위 {range_start} ~ {range_end} 처리 중 HTTP 오류: {e}")
                # 실패한 범위 정보 기록
                progress.setdefault("failed_ranges", []).append({
                    "range_id": range_id,
                    "error": str(e),
                    "error_time": datetime.now().isoformat()
                })
                self.save_progress(progress)
                continue
                
            except Exception as e:
                logger.error(f"날짜 범위 {range_start} ~ {range_end} 처리 오류: {e}")
                # 실패한 범위 정보 기록
                progress.setdefault("failed_ranges", []).append({
                    "range_id": range_id,
                    "error": str(e),
                    "error_time": datetime.now().isoformat()
                })
                self.save_progress(progress)
                continue
        
        # 마지막 청크 저장
        if current_chunk:
            chunk_id = f"{chunk_counter:04d}"
            self.save_tickets_chunk(current_chunk, chunk_id)
            progress.setdefault("chunks_completed", []).append(chunk_id)
        
        # RAW 데이터 수집 (선택사항)
        logger.info("=== RAW 데이터 수집 단계 시작 ===")
        logger.info(f"RAW 데이터 수집 설정: details={collect_raw_details}, conversations={collect_raw_conversations}, kb={collect_raw_kb}, attachments={collect_raw_attachments}")
        logger.info(f"수집된 티켓 ID 수: {len(collected_ticket_ids)}")
        
        # 디버깅을 위한 상세 정보
        if collected_ticket_ids:
            logger.info(f"수집된 티켓 ID 목록 (처음 10개): {collected_ticket_ids[:10]}")
        else:
            logger.warning("❌ 티켓 ID가 하나도 수집되지 않았습니다!")
            logger.warning("이는 다음 원인일 수 있습니다:")
            logger.warning("  1. 날짜 범위에 해당하는 티켓이 없음")
            logger.warning("  2. API 호출이 실패함")
            logger.warning("  3. 티켓 필터링 조건에 맞는 티켓이 없음")
        
        raw_stats = {}
        logger.info(f"🔍 [DEBUG] Raw 데이터 수집 시작 - collected_ticket_ids 수: {len(collected_ticket_ids) if collected_ticket_ids else 0}")
        logger.info(f"🔍 [DEBUG] 수집 플래그 상태: collect_raw_details={collect_raw_details}, collect_raw_conversations={collect_raw_conversations}")
        
        if collect_raw_details and collected_ticket_ids:
            logger.info("티켓 상세정보 raw 데이터 수집 시작...")
            logger.info(f"🔍 [DEBUG] collect_raw_ticket_details 호출 준비 - 티켓 ID 수: {len(collected_ticket_ids)}")
            try:
                success_count = await self.collect_raw_ticket_details(collected_ticket_ids, progress)
                raw_stats["ticket_details_collected"] = success_count
                logger.info("✅ 티켓 상세정보 raw 데이터 수집 완료")
                logger.info(f"🔍 [DEBUG] collect_raw_ticket_details 완료 - 처리된 티켓 수: {success_count}")
            except Exception as e:
                logger.error(f"❌ 티켓 상세정보 raw 데이터 수집 중 오류: {e}")
                logger.error(f"🔍 [DEBUG] collect_raw_ticket_details 예외: {type(e).__name__}: {e}")
                raw_stats["ticket_details_error"] = str(e)
        elif not collect_raw_details:
            logger.info("티켓 상세정보 raw 데이터 수집이 비활성화되어 건너뜁니다.")
            logger.info(f"🔍 [DEBUG] collect_raw_details=False 이므로 티켓 상세정보 수집 건너뜀")
        elif not collected_ticket_ids:
            logger.warning("수집된 티켓 ID가 없어 티켓 상세정보 raw 데이터 수집을 건너뜁니다.")
            logger.warning(f"🔍 [DEBUG] collected_ticket_ids가 비어있어 티켓 상세정보 수집 건너뜀")
        
        if collect_raw_conversations and collected_ticket_ids:
            logger.info("티켓 대화내역 raw 데이터 수집 시작...")
            try:
                conversations_count = await self.collect_raw_conversations(collected_ticket_ids, progress)
                raw_stats["conversations_collected"] = conversations_count
                logger.info("✅ 티켓 대화내역 raw 데이터 수집 완료")
                logger.info(f"🔍 [DEBUG] collect_raw_conversations 완료 - 수집된 대화 수: {conversations_count}")
            except Exception as e:
                logger.error(f"❌ 티켓 대화내역 raw 데이터 수집 중 오류: {e}")
                raw_stats["conversations_error"] = str(e)
        elif not collect_raw_conversations:
            logger.info("티켓 대화내역 raw 데이터 수집이 비활성화되어 건너뜁니다.")
        elif not collected_ticket_ids:
            logger.warning("수집된 티켓 ID가 없어 티켓 대화내역 raw 데이터 수집을 건너뜁니다.")
        
        # 첨부파일 수집 추가 - collect_raw_attachments가 True인 경우 항상 수집
        if collect_raw_attachments and collected_ticket_ids:
            logger.info("티켓 첨부파일 raw 데이터 수집 시작...")
            try:
                attachments_count = await self.collect_raw_attachments(collected_ticket_ids, progress)
                raw_stats["attachments_collected"] = attachments_count
                logger.info("✅ 티켓 첨부파일 raw 데이터 수집 완료")
                logger.info(f"🔍 [DEBUG] collect_raw_attachments 완료 - 첨부파일이 있는 티켓 수: {attachments_count}")
            except Exception as e:
                logger.error(f"❌ 티켓 첨부파일 raw 데이터 수집 중 오류: {e}")
                raw_stats["attachments_error"] = str(e)
        elif not collect_raw_attachments:
            logger.info("첨부파일 raw 데이터 수집이 비활성화되어 건너뜁니다.")
        elif not collected_ticket_ids:
            logger.warning("수집된 티켓 ID가 없어 첨부파일 raw 데이터 수집을 건너뜁니다.")
        
        if collect_raw_kb:
            logger.info("지식베이스 raw 데이터 수집 시작...")
            try:
                kb_articles_count = await self.collect_raw_knowledge_base(progress, max_articles=max_kb_articles)
                raw_stats["knowledge_base_collected"] = kb_articles_count
                if max_kb_articles:
                    raw_stats["max_kb_articles"] = max_kb_articles
                logger.info("✅ 지식베이스 raw 데이터 수집 완료")
                logger.info(f"🔍 [DEBUG] collect_raw_knowledge_base 완료 - 수집된 문서 수: {kb_articles_count}")
            except Exception as e:
                logger.error(f"❌ 지식베이스 raw 데이터 수집 중 오류: {e}")
                raw_stats["knowledge_base_error"] = str(e)
        else:
            logger.info("지식베이스 raw 데이터 수집이 비활성화되어 건너뜁니다.")
        
        logger.info(f"=== RAW 데이터 수집 단계 완료: {raw_stats} ===")
        
        # 디버깅용 진단 정보 저장
        diagnostic_info = {
            "collection_timestamp": datetime.now().isoformat(),
            "total_tickets_collected": total_tickets,
            "collected_ticket_ids_count": len(collected_ticket_ids),
            "collected_ticket_ids_sample": collected_ticket_ids[:10] if collected_ticket_ids else [],
            "raw_data_settings": {
                "collect_raw_details": collect_raw_details,
                "collect_raw_conversations": collect_raw_conversations,
                "collect_raw_kb": collect_raw_kb,
                "collect_raw_attachments": collect_raw_attachments
            },
            "raw_data_stats": raw_stats,
            "date_ranges_processed": len(progress.get("completed_ranges", [])),
            "total_date_ranges": len(date_ranges)
        }
        
        diagnostic_file = self.output_dir / "diagnostic_info.json"
        try:
            with open(diagnostic_file, 'w', encoding='utf-8') as f:
                json.dump(diagnostic_info, f, ensure_ascii=False, indent=2)
            logger.info(f"진단 정보 저장됨: {diagnostic_file}")
        except Exception as e:
            logger.error(f"진단 정보 저장 실패: {e}")
        
        # Raw 데이터 디렉토리 상태 확인 및 로깅
        logger.info("=== Raw 데이터 디렉토리 최종 상태 ===")
        for sub_dir in ["ticket_details", "conversations", "knowledge_base", "attachments"]:
            sub_path = self.raw_data_dir / sub_dir
            if sub_path.exists():
                files = list(sub_path.glob("*.json"))
                total_size = sum(f.stat().st_size for f in files)
                logger.info(f"{sub_dir}: {len(files)}개 파일, 총 {total_size:,} bytes")
                for file in files:
                    logger.info(f"  - {file.name} ({file.stat().st_size:,} bytes)")
            else:
                logger.warning(f"{sub_dir}: 디렉토리 없음 또는 파일 없음")
        
        # 최종 통계
        stats = {
            "total_tickets_collected": total_tickets,
            "chunks_created": chunk_counter + (1 if current_chunk else 0),
            "date_ranges_processed": len(progress.get("completed_ranges", [])),
            "collection_completed": datetime.now().isoformat(),
            "days_per_chunk": days_per_chunk,
            "adaptive_rate": adaptive_rate,
            "final_request_delay": self.REQUEST_DELAY if adaptive_rate else "N/A",
            "raw_data_stats": raw_stats
        }
        
        # 통계 저장
        with open(self.output_dir / "collection_stats.json", 'w') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        
        logger.info(f"수집 완료: 총 {total_tickets:,}개 티켓")
        if raw_stats:
            logger.info(f"RAW 데이터 수집 통계: {raw_stats}")
        return stats

    async def split_large_ticket_chunks(self):
        """
        기존의 큰 티켓 청크 파일들을 RAW_DATA_CHUNK_SIZE 기준으로 재분할합니다.
        특히 250MB 같은 큰 파일을 작은 청크들로 나눕니다.
        """
        logger.info("=== 큰 티켓 청크 파일 분할 시작 ===")
        
        tickets_dir = self.raw_data_dir / "tickets"
        if not tickets_dir.exists():
            logger.warning("티켓 디렉토리가 존재하지 않습니다.")
            return
        
        # 기존 청크 파일들을 크기순으로 정렬
        chunk_files = list(tickets_dir.glob("tickets_chunk_*.json"))
        if not chunk_files:
            logger.info("분할할 티켓 청크 파일이 없습니다.")
            return
            
        logger.info(f"총 {len(chunk_files)}개 청크 파일 발견")
        
        # 백업 디렉토리 생성
        backup_dir = tickets_dir.parent / "tickets_backup"
        backup_dir.mkdir(exist_ok=True)
        
        total_processed = 0
        new_chunk_counter = 0
        
        for chunk_file in sorted(chunk_files):
            # 파일 크기 확인
            file_size_mb = chunk_file.stat().st_size / (1024 * 1024)
            logger.info(f"처리 중: {chunk_file.name} ({file_size_mb:.1f}MB)")
            
            # 50MB 이상의 파일만 분할
            if file_size_mb < 50:
                logger.info(f"  → 크기가 작아 분할하지 않음 ({file_size_mb:.1f}MB)")
                continue
                
            try:
                # 기존 파일 로드
                with open(chunk_file, 'r', encoding='utf-8') as f:
                    tickets = json.load(f)
                
                logger.info(f"  → {len(tickets)}개 티켓 로드됨, 분할 시작...")
                
                # 기존 파일을 백업으로 이동
                backup_file = backup_dir / chunk_file.name
                shutil.move(str(chunk_file), str(backup_file))
                logger.info(f"  → 백업 생성: {backup_file}")
                
                # RAW_DATA_CHUNK_SIZE 단위로 분할
                for i in range(0, len(tickets), self.RAW_DATA_CHUNK_SIZE):
                    chunk_tickets = tickets[i:i + self.RAW_DATA_CHUNK_SIZE]
                    new_chunk_id = f"{new_chunk_counter:04d}"
                    
                    # 새 청크 저장
                    self.save_tickets_chunk(chunk_tickets, new_chunk_id)
                    new_chunk_counter += 1
                    total_processed += len(chunk_tickets)
                    
                    logger.info(f"  → 새 청크 생성: tickets_chunk_{new_chunk_id}.json ({len(chunk_tickets)}개 티켓)")
                
                logger.info(f"분할 완료: {chunk_file.name} → {len(tickets) // self.RAW_DATA_CHUNK_SIZE + (1 if len(tickets) % self.RAW_DATA_CHUNK_SIZE else 0)}개 새 청크")
                
            except Exception as e:
                logger.error(f"청크 파일 분할 실패 {chunk_file.name}: {e}")
                continue
        
        logger.info(f"=== 청크 분할 완료 ===")
        logger.info(f"총 처리된 티켓 수: {total_processed}개")
        logger.info(f"생성된 새 청크 수: {new_chunk_counter}개")
        logger.info(f"백업 위치: {backup_dir}")
        
        # 진행 상황 업데이트 (새로운 청크 ID들로)
        progress = self.load_progress()
        new_chunk_ids = [f"{i:04d}" for i in range(new_chunk_counter)]
        progress["chunks_completed"] = new_chunk_ids
        progress["chunk_split_completed"] = True
        progress["chunk_split_timestamp"] = datetime.now().isoformat()
        self.save_progress(progress)
        
        logger.info("진행 상황 업데이트 완료")


async def main():
    """전체 데이터 수집 함수 - freshdesk_full_data 디렉토리 사용"""
    output_dir = "freshdesk_full_data"
    async with OptimizedFreshdeskFetcher(output_dir) as fetcher:
        stats = await fetcher.collect_all_tickets(
            start_date="2015-01-01",  # 가능한 가장 오래된 날짜부터
            end_date=None,  # 현재까지
            include_conversations=True,  # 대화내역 항상 포함
            include_attachments=True,   # 첨부파일 정보 항상 포함
            max_tickets=None,  # 무제한 수집
            collect_raw_details=True,   # 티켓 상세정보 raw 데이터 수집
            collect_raw_conversations=True,  # 대화내역 raw 데이터 수집
            collect_raw_attachments=True,  # 첨부파일 raw 데이터 수집
            collect_raw_kb=True  # 지식베이스 raw 데이터 수집
        )
        
        print(f"수집 통계: {stats}")


async def test_collection_limit():
    """100개 티켓 제한 테스트"""
    logging.info("======= 100개 티켓 제한 테스트 시작 =======")
    output_dir = "freshdesk_test_data"
    max_tickets = 100
    
    # 테스트 디렉토리 생성
    Path(output_dir).mkdir(exist_ok=True)
    
    start_time = datetime.now()
    async with OptimizedFreshdeskFetcher(output_dir) as fetcher:
        stats = await fetcher.collect_all_tickets(
            start_date="2015-01-01",
            end_date=None,
            include_conversations=True,
            include_attachments=True,  # 첨부파일도 항상 포함
            max_tickets=max_tickets,  # 100개로 제한
            max_kb_articles=max_tickets,  # 지식베이스도 100개로 제한
            days_per_chunk=7,         # 테스트에서는 7일 단위로 분할
            adaptive_rate=True,       # 적응형 속도 조절 활성화
            collect_raw_details=True, # 테스트에서도 raw 데이터 수집
            collect_raw_conversations=True,
            collect_raw_attachments=True,  # 첨부파일 raw 데이터 수집
            collect_raw_kb=True
        )
    
    elapsed = datetime.now() - start_time
    logging.info(f"테스트 완료: {stats}")
    logging.info(f"소요 시간: {elapsed}")
    logging.info(f"수집된 티켓 수: {stats['total_tickets_collected']:,}")
    logging.info("=============================================")
    logging.info(f"수집된 티켓 수: {stats['total_tickets_collected']}")
    logging.info("============================================")


async def collect_only_raw_data():
    """
    기존 티켓 기본정보를 사용하여 raw 데이터만 수집하는 함수
    티켓 기본정보가 이미 수집된 상태에서 상세정보와 지식베이스만 추가로 수집
    """
    logging.info("======= RAW 데이터만 수집 모드 =======")
    output_dir = "freshdesk_full_data"
    
    async with OptimizedFreshdeskFetcher(output_dir) as fetcher:
        progress = fetcher.load_progress()
        
        # 기존 티켓 청크 파일에서 티켓 ID 추출
        ticket_ids = []
        chunks_completed = progress.get("chunks_completed", [])
        
        if not chunks_completed:
            logger.error("기존 티켓 데이터가 없습니다. 먼저 티켓 기본정보를 수집하세요.")
            return
        
        logger.info(f"기존 {len(chunks_completed)}개 청크에서 티켓 ID 추출 중...")
        
        for chunk_id in chunks_completed:
            # raw_data/tickets/ 디렉토리에서만 청크 파일 찾기 (현재 구조만 지원)
            chunk_file = fetcher.raw_data_dir / "tickets" / f"tickets_chunk_{chunk_id}.json"
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
                logger.warning("모든 청크 파일은 raw_data/tickets/ 디렉토리에 있어야 합니다")
        
        logger.info(f"총 {len(ticket_ids)}개 티켓 ID 추출 완료")
        
        if ticket_ids:
            # 티켓 상세정보 수집
            await fetcher.collect_raw_ticket_details(ticket_ids, progress)
            
            # 대화내역 수집
            await fetcher.collect_raw_conversations(ticket_ids, progress)
            
            # 지식베이스 수집 (max_articles=None으로 전달하여 모든 문서 수집)
            await fetcher.collect_raw_knowledge_base(progress, max_articles=None)
            
            logger.info("RAW 데이터 수집 완료")
        else:
            logger.error("추출된 티켓 ID가 없습니다.")


async def split_existing_chunks():
    """
    기존의 큰 티켓 청크 파일들을 작은 청크로 분할하는 유틸리티 함수
    250MB 같은 큰 파일을 1000개 단위의 작은 청크로 분할합니다.
    """
    logging.info("======= 기존 청크 파일 분할 시작 =======")
    output_dir = "freshdesk_full_data"
    
    async with OptimizedFreshdeskFetcher(output_dir) as fetcher:
        await fetcher.split_large_ticket_chunks()
    
    logging.info("======= 청크 파일 분할 완료 =======")


if __name__ == "__main__":
    import sys
    
    # 명령행 인수 처리
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        
        if command == "split":
            # 기존 큰 청크 파일들을 작은 청크로 분할
            print("기존 청크 파일 분할을 시작합니다...")
            asyncio.run(split_existing_chunks())
        
        elif command == "raw":
            # RAW 데이터만 수집
            print("RAW 데이터 수집을 시작합니다...")
            asyncio.run(collect_only_raw_data())
        
        elif command == "test":
            # 제한된 수량으로 테스트
            print("제한된 수량으로 테스트를 시작합니다...")
            asyncio.run(test_collection_limit())
        
        elif command == "full":
            # 전체 데이터 수집
            print("전체 데이터 수집을 시작합니다...")
            asyncio.run(main())
        
        else:
            print("사용법:")
            print("  python optimized_fetcher.py split    # 기존 큰 청크 파일 분할")
            print("  python optimized_fetcher.py raw      # RAW 데이터만 수집")
            print("  python optimized_fetcher.py test     # 제한된 수량으로 테스트")
            print("  python optimized_fetcher.py full     # 전체 데이터 수집")
    else:
        # 기본 동작: RAW 데이터 수집
        print("기본 모드: RAW 데이터 수집을 시작합니다...")
        print("다른 옵션을 사용하려면 'python optimized_fetcher.py --help' 참조")
        asyncio.run(collect_only_raw_data())
