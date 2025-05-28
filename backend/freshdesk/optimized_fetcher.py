"""
최적화된 Freshdesk 대용량 데이터 수집기

무제한 티켓 데이터를 효율적으로 수집하기 위한 최적화된 접근법
"""
import os
import httpx
import asyncio
import logging
from typing import List, Dict
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


class OptimizedFreshdeskFetcher:
    """
    대용량 티켓 데이터 수집을 위한 최적화된 클래스
    """
    
    def __init__(self, output_dir: str = "freshdesk_data"):
        # output_dir이 절대경로가 아니면 backend/ 기준으로 보정
        output_path = Path(output_dir)
        if not output_path.is_absolute():
            # backend/ 하위로 강제
            backend_root = Path(__file__).parent.parent
            output_path = backend_root / output_path
        self.output_dir = output_path.resolve()
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
        include_attachments: bool = False,
        max_tickets: int = None,
        current_total: int = 0
    ) -> List[Dict]:
        """특정 날짜 범위의 티켓 수집"""
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
                
                # 종료 날짜를 넘어선 티켓이 있으면 중단
                if len(batch_tickets) > len(filtered_tickets):
                    logger.info(f"날짜 범위 종료점 도달 (페이지 {page})")
                    break
                    
                if len(batch_tickets) < PER_PAGE or (remaining_tickets is not None and len(tickets) >= remaining_tickets):
                    break
                    
                page += 1
                await asyncio.sleep(REQUEST_DELAY)
                
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
                        conversations = await fetch_ticket_conversations(None, ticket_id)
                        ticket["conversations"] = conversations
                if include_attachments:
                    # 안전하게 attachments 접근 (None이거나 존재하지 않는 경우 방지)
                    attachments = ticket.get("attachments", []) or ticket.get("all_attachments", [])
                    if not attachments:
                        from .fetcher import fetch_ticket_attachments
                        attachments = await fetch_ticket_attachments(None, ticket_id)
                        # None이 아닌 경우에만 할당 (빈 리스트도 유효한 값으로 간주)
                        if attachments is not None:
                            ticket["attachments"] = attachments
                enriched_tickets.append(ticket)
            except Exception as e:
                logger.error(f"티켓 {ticket_id} 추가 정보 수집 오류: {e}")
                enriched_tickets.append(ticket)
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
        
        if max_tickets is not None:
            logger.info(f"최대 {max_tickets}개 티켓만 수집합니다")
        
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
            if range_id in progress.get("completed_ranges", []):
                logger.info(f"날짜 범위 {range_start} ~ {range_end} 이미 처리됨, 건너뜀")
                continue
            
            try:
                # 현재까지 수집된 티켓 수를 전달하여 페이지별로 제한 적용
                tickets = await self.fetch_tickets_by_date_range(
                    range_start, range_end, 
                    include_conversations, include_attachments,
                    max_tickets=max_tickets,  # 최대 티켓 수 전달
                    current_total=total_tickets  # 현재까지 수집된 티켓 수 전달
                )
                
                current_chunk.extend(tickets)
                total_tickets += len(tickets)
                
                # max_tickets에 도달했으면 더 이상 수집하지 않음
                if max_tickets is not None and total_tickets >= max_tickets:
                    logger.info(f"최대 티켓 수({max_tickets})에 정확히 도달, 수집 완료")
                    # 진행 상황 업데이트 후 종료
                    if range_id not in progress.get("completed_ranges", []):
                        progress.setdefault("completed_ranges", []).append(range_id)
                    progress["total_collected"] = total_tickets
                    progress["last_updated"] = datetime.now().isoformat()
                    self.save_progress(progress)
                    break
                
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
    """전체 데이터 수집 함수 - freshdesk_full_data 디렉토리 사용"""
    output_dir = "freshdesk_full_data"
    async with OptimizedFreshdeskFetcher(output_dir) as fetcher:
        stats = await fetcher.collect_all_tickets(
            start_date="2015-01-01",  # 가능한 가장 오래된 날짜부터
            end_date=None,  # 현재까지
            include_conversations=True,  # 대화내역 항상 포함
            include_attachments=True,   # 첨부파일 정보 항상 포함
            max_tickets=None  # 무제한 수집
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
            max_tickets=max_tickets  # 100개로 제한
        )
    
    elapsed = datetime.now() - start_time
    logging.info(f"테스트 완료: {stats}")
    logging.info(f"소요 시간: {elapsed}")
    logging.info(f"수집된 티켓 수: {stats['total_tickets_collected']}")
    logging.info("============================================")


if __name__ == "__main__":
    # 기본 호출은 main()이지만, 테스트를 원할 경우 test_collection_limit() 호출
    # asyncio.run(main())
    asyncio.run(test_collection_limit())
