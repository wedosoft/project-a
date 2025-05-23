"""
최적화된 Freshdesk 대용량 데이터 수집기

무제한 티켓 데이터를 효율적으로 수집하기 위한 최적화된 접근법
"""
import os
import httpx
import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import json
from pathlib import Path
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

FRESHDESK_DOMAIN = os.getenv("FRESHDESK_DOMAIN")
FRESHDESK_API_KEY = os.getenv("FRESHDESK_API_KEY")

if not FRESHDESK_DOMAIN or not FRESHDESK_API_KEY:
    raise RuntimeError("FRESHDESK_DOMAIN, FRESHDESK_API_KEY 환경 변수가 필요합니다.")

BASE_URL = f"https://{FRESHDESK_DOMAIN}.freshdesk.com/api/v2"
HEADERS = {"Content-Type": "application/json"}
AUTH = (FRESHDESK_API_KEY, "X")

# 최적화된 설정
MAX_RETRIES = 5
RETRY_DELAY = 2
PER_PAGE = 100  # 최대값 사용
REQUEST_DELAY = 0.3  # Enterprise 기준 200req/min → 300ms 간격

# 청크 기반 처리 설정
CHUNK_SIZE = 10000  # 청크당 티켓 수
SAVE_INTERVAL = 1000  # 1000개마다 중간 저장


class OptimizedFreshdeskFetcher:
    """
    대용량 티켓 데이터 수집을 위한 최적화된 클래스
    """
    
    def __init__(self, output_dir: str = "freshdesk_data"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.progress_file = self.output_dir / "progress.json"
        self.client = None
        
    async def __aenter__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()

    def save_progress(self, progress_data: Dict):
        """진행 상황을 파일에 저장"""
        with open(self.progress_file, 'w') as f:
            json.dump(progress_data, f, indent=2)
            
    def load_progress(self) -> Dict:
        """저장된 진행 상황 로드"""
        if self.progress_file.exists():
            with open(self.progress_file, 'r') as f:
                return json.load(f)
        return {"last_updated": None, "total_collected": 0, "chunks_completed": []}

    async def fetch_with_retry(self, url: str, params: Dict = None) -> Dict:
        """재시도 로직이 포함된 API 호출"""
        retries = 0
        while retries < MAX_RETRIES:
            try:
                resp = await self.client.get(url, headers=HEADERS, auth=AUTH, params=params)
                
                # Rate limit 체크
                if resp.status_code == 429:
                    retry_after = int(resp.headers.get('Retry-After', 60))
                    logger.warning(f"Rate limit 도달. {retry_after}초 대기 중...")
                    await asyncio.sleep(retry_after)
                    retries += 1
                    continue
                    
                resp.raise_for_status()
                return resp.json()
                
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP 오류 {e.response.status_code}: {e}")
                if e.response.status_code in [500, 502, 503, 504]:
                    retries += 1
                    wait_time = RETRY_DELAY * (2 ** retries)
                    logger.info(f"{wait_time}초 대기 후 재시도...")
                    await asyncio.sleep(wait_time)
                else:
                    raise
                    
            except Exception as e:
                logger.error(f"요청 오류: {e}")
                retries += 1
                if retries < MAX_RETRIES:
                    wait_time = RETRY_DELAY * (2 ** retries)
                    await asyncio.sleep(wait_time)
                else:
                    raise

    def get_date_ranges(self, start_date: str = "2015-01-01", end_date: str = None) -> List[tuple]:
        """
        30일 단위로 날짜 범위를 분할하여 반환
        (Freshdesk 30일 제한 우회)
        """
        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")
            
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        
        ranges = []
        current = start
        
        while current < end:
            range_end = min(current + timedelta(days=29), end)
            ranges.append((
                current.strftime("%Y-%m-%dT00:00:00Z"),
                range_end.strftime("%Y-%m-%dT23:59:59Z")
            ))
            current = range_end + timedelta(days=1)
            
        return ranges

    async def fetch_tickets_by_date_range(
        self, 
        start_date: str, 
        end_date: str,
        include_conversations: bool = False,
        include_attachments: bool = False
    ) -> List[Dict]:
        """특정 날짜 범위의 티켓 수집"""
        tickets = []
        page = 1
        
        logger.info(f"날짜 범위 {start_date} ~ {end_date} 수집 시작")
        
        while True:
            params = {
                "page": page,
                "per_page": PER_PAGE,
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
                
                # 추가 정보 수집
                if include_conversations or include_attachments:
                    filtered_tickets = await self.enrich_tickets(
                        filtered_tickets, include_conversations, include_attachments
                    )
                
                tickets.extend(filtered_tickets)
                
                # 종료 날짜를 넘어선 티켓이 있으면 중단
                if len(batch_tickets) > len(filtered_tickets):
                    logger.info(f"날짜 범위 종료점 도달 (페이지 {page})")
                    break
                    
                if len(batch_tickets) < PER_PAGE:
                    break
                    
                page += 1
                await asyncio.sleep(REQUEST_DELAY)
                
                logger.info(f"페이지 {page-1} 완료: {len(filtered_tickets)}개 티켓")
                
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
        """티켓에 대화내역과 첨부파일 정보 추가"""
        enriched_tickets = []
        
        for ticket in tickets:
            ticket_id = ticket.get("id")
            
            try:
                if include_conversations:
                    conversations = await self.fetch_with_retry(
                        f"{BASE_URL}/tickets/{ticket_id}/conversations"
                    )
                    ticket["conversations"] = conversations
                    await asyncio.sleep(REQUEST_DELAY)
                
                if include_attachments:
                    # 티켓 상세 정보에서 첨부파일 추출
                    ticket_detail = await self.fetch_with_retry(
                        f"{BASE_URL}/tickets/{ticket_id}"
                    )
                    ticket["attachments"] = ticket_detail.get("attachments", [])
                    await asyncio.sleep(REQUEST_DELAY)
                    
                enriched_tickets.append(ticket)
                
            except Exception as e:
                logger.error(f"티켓 {ticket_id} 추가 정보 수집 오류: {e}")
                enriched_tickets.append(ticket)  # 기본 정보라도 저장
                
        return enriched_tickets

    def save_tickets_chunk(self, tickets: List[Dict], chunk_id: str):
        """티켓 청크를 파일로 저장"""
        chunk_file = self.output_dir / f"tickets_chunk_{chunk_id}.json"
        with open(chunk_file, 'w', encoding='utf-8') as f:
            json.dump(tickets, f, ensure_ascii=False, indent=2)
        logger.info(f"청크 {chunk_id} 저장 완료: {len(tickets)}개 티켓")

    async def collect_all_tickets(
        self,
        start_date: str = "2015-01-01",
        end_date: str = None,
        include_conversations: bool = False,
        include_attachments: bool = False,
        max_tickets: int = None,
        resource_check_func = None,
        resource_check_interval: int = 1000
    ) -> Dict:
        """
        모든 티켓을 효율적으로 수집
        
        Returns:
            수집 통계 정보
        """
        progress = self.load_progress()
        date_ranges = self.get_date_ranges(start_date, end_date)
        
        total_tickets = 0
        chunk_counter = 0
        current_chunk = []
        
        logger.info(f"총 {len(date_ranges)}개 날짜 범위로 분할하여 수집 시작")
        
        for i, (range_start, range_end) in enumerate(date_ranges):
            # 최대 티켓 수 제한이 있을 경우만 체크
            if max_tickets is not None and total_tickets >= max_tickets:
                logger.info(f"최대 티켓 수({max_tickets})에 도달")
                break
                
            # 시스템 리소스 체크
            if resource_check_func and i % resource_check_interval == 0 and i > 0:
                if not resource_check_func():
                    logger.warning("시스템 리소스 부족으로 수집 일시 중단")
                    break
                
            # 이미 처리된 날짜 범위는 건너뛰기
            range_id = f"{range_start}_{range_end}"
            if range_id in progress.get("completed_ranges", []):
                logger.info(f"날짜 범위 {range_start} ~ {range_end} 이미 처리됨, 건너뜀")
                continue
            
            try:
                tickets = await self.fetch_tickets_by_date_range(
                    range_start, range_end, include_conversations, include_attachments
                )
                
                current_chunk.extend(tickets)
                total_tickets += len(tickets)
                
                # 청크 크기에 도달하면 저장
                if len(current_chunk) >= CHUNK_SIZE:
                    self.save_tickets_chunk(current_chunk, f"{chunk_counter:04d}")
                    chunk_counter += 1
                    current_chunk = []
                
                # 진행 상황 업데이트
                if range_id not in progress.get("completed_ranges", []):
                    progress.setdefault("completed_ranges", []).append(range_id)
                progress["total_collected"] = total_tickets
                progress["last_updated"] = datetime.now().isoformat()
                self.save_progress(progress)
                
                logger.info(f"진행률: {i+1}/{len(date_ranges)} ({total_tickets}개 수집)")
                
            except Exception as e:
                logger.error(f"날짜 범위 {range_start} ~ {range_end} 처리 오류: {e}")
                continue
        
        # 마지막 청크 저장
        if current_chunk:
            self.save_tickets_chunk(current_chunk, f"{chunk_counter:04d}")
        
        # 최종 통계
        stats = {
            "total_tickets_collected": total_tickets,
            "chunks_created": chunk_counter + (1 if current_chunk else 0),
            "date_ranges_processed": len(progress.get("completed_ranges", [])),
            "collection_completed": datetime.now().isoformat()
        }
        
        # 통계 저장
        with open(self.output_dir / "collection_stats.json", 'w') as f:
            json.dump(stats, f, indent=2)
        
        logger.info(f"수집 완료: 총 {total_tickets}개 티켓")
        return stats


async def main():
    """사용 예제"""
    async with OptimizedFreshdeskFetcher("freshdesk_full_data") as fetcher:
        stats = await fetcher.collect_all_tickets(
            start_date="2015-01-01",  # 가능한 가장 오래된 날짜부터
            end_date=None,  # 현재까지
            include_conversations=True,  # 대화내역 포함 여부
            include_attachments=False,  # 첨부파일 정보 포함 여부
            max_tickets=None  # 무제한 수집
        )
        
        print(f"수집 통계: {stats}")


if __name__ == "__main__":
    asyncio.run(main())
