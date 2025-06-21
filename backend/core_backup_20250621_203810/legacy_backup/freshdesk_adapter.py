"""
Freshdesk 플랫폼 어댑터 구현
기존 optimized_fetcher.py의 로직을 플랫폼 어댑터 패턴으로 리팩토링
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
import httpx
from datetime import datetime

from .platform_adapter import PlatformAdapter

logger = logging.getLogger(__name__)


class FreshdeskAdapter(PlatformAdapter):
    """
    Freshdesk API를 위한 플랫폼 어댑터
    기존 optimized_fetcher.py의 Freshdesk 로직을 재사용하면서 추상화 적용
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        # Freshdesk 전용 설정
        self.base_url = self._build_base_url()
        self.auth = (self.api_key, "X")
        self.headers = {
            "Content-Type": "application/json",
            "X-Company-ID": self.company_id,
            "X-Platform": "freshdesk"
        }
        
        # 기존 optimized_fetcher.py의 설정값들 재사용
        self.max_retries = config.get("max_retries", 5)
        self.retry_delay = config.get("retry_delay", 2)
        self.request_delay = config.get("request_delay", 0.3)
        self.per_page = config.get("per_page", 100)
        
        # HTTP 클라이언트 초기화는 async context에서 수행
        self.client: Optional[httpx.AsyncClient] = None
    
    def _build_base_url(self) -> str:
        """
        Freshdesk API base URL 구성
        기존 optimized_fetcher.py의 로직 재사용
        """
        if ".freshdesk.com" in self.domain:
            base_url = f"https://{self.domain}"
        else:
            base_url = f"https://{self.domain}.freshdesk.com"
        return f"{base_url}/api/v2"
    
    async def __aenter__(self):
        """Async context manager 진입"""
        self.client = httpx.AsyncClient(timeout=30.0)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager 종료"""
        if self.client:
            await self.client.aclose()
    
    async def fetch_with_retry(self, url: str, params: Optional[Dict] = None) -> Dict:
        """
        재시도 로직이 포함된 API 호출
        기존 optimized_fetcher.py의 fetch_with_retry 메서드 재사용
        """
        if not self.client:
            raise RuntimeError("HTTP 클라이언트가 초기화되지 않았습니다. async with 구문을 사용하세요.")
        
        retries = 0
        while retries < self.max_retries:
            try:
                resp = await self.client.get(url, headers=self.headers, auth=self.auth, params=params)
                
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
                    wait_time = self.retry_delay * (2 ** retries)
                    logger.info(f"{wait_time}초 대기 후 재시도 ({retries}/{self.max_retries})...")
                    await asyncio.sleep(wait_time)
                else:
                    raise
                    
            except Exception as e:
                logger.error(f"요청 오류: {e}")
                retries += 1
                if retries < self.max_retries:
                    wait_time = self.retry_delay * (2 ** retries)
                    logger.info(f"요청 오류 발생 후 {wait_time}초 대기 후 재시도 ({retries}/{self.max_retries})...")
                    await asyncio.sleep(wait_time)
                else:
                    raise
        
        # 최대 재시도 횟수 초과
        raise Exception(f"최대 재시도 횟수({self.max_retries})에 도달했습니다: {url}")
    
    async def fetch_tickets_by_date_range(
        self, 
        start_date: str, 
        end_date: str, 
        page: int = 1, 
        per_page: int = 100
    ) -> List[Dict]:
        """
        날짜 범위로 티켓 목록 조회
        기존 optimized_fetcher.py의 fetch_tickets_by_date_range 로직 활용
        """
        params = {
            "page": page,
            "per_page": min(per_page, self.per_page),
            "updated_since": start_date,
            "order_by": "updated_at",
            "order_type": "asc"
        }
        
        try:
            batch_tickets = await self.fetch_with_retry(f"{self.base_url}/tickets", params)
            
            if not batch_tickets:
                return []
            
            # 종료 날짜 이후 티켓 필터링
            filtered_tickets = [
                t for t in batch_tickets 
                if t.get('updated_at', '') <= end_date
            ]
            
            # 정규화 적용
            normalized_tickets = []
            for ticket in filtered_tickets:
                normalized_ticket = self.normalize_ticket(ticket)
                normalized_tickets.append(normalized_ticket)
            
            await asyncio.sleep(self.request_delay)
            return normalized_tickets
            
        except Exception as e:
            logger.error(f"티켓 목록 조회 실패 (페이지 {page}): {e}")
            return []
    
    async def fetch_ticket_details(self, ticket_id: str) -> Optional[Dict]:
        """
        티켓 상세정보 조회
        기존 optimized_fetcher.py의 fetch_ticket_detail_raw 로직 활용
        """
        try:
            detail = await self.fetch_with_retry(f"{self.base_url}/tickets/{ticket_id}")
            await asyncio.sleep(self.request_delay)
            
            if detail:
                return self.normalize_ticket(detail)
            return None
            
        except Exception as e:
            logger.error(f"티켓 {ticket_id} 상세정보 조회 실패: {e}")
            return None
    
    async def fetch_conversations(self, ticket_id: str) -> List[Dict]:
        """
        티켓 대화내역 조회
        기존 optimized_fetcher.py의 fetch_conversations_raw 로직 활용
        """
        try:
            conversations = await self.fetch_with_retry(f"{self.base_url}/tickets/{ticket_id}/conversations")
            await asyncio.sleep(self.request_delay)
            
            # API 응답이 dict인 경우 빈 리스트 반환, list인 경우 그대로 반환
            if isinstance(conversations, dict):
                return []
            
            if not conversations:
                return []
            
            # 정규화 적용
            normalized_conversations = []
            for conv in conversations:
                conv["ticket_id"] = ticket_id  # 티켓 ID 추가
                normalized_conv = self.normalize_conversation(conv)
                normalized_conversations.append(normalized_conv)
            
            return normalized_conversations
            
        except Exception as e:
            logger.error(f"티켓 {ticket_id} 대화내역 조회 실패: {e}")
            return []
    
    async def fetch_attachments(self, ticket_id: str) -> List[Dict]:
        """
        티켓 첨부파일 정보 조회
        기존 optimized_fetcher.py의 fetch_attachments_raw 로직 활용
        """
        try:
            # Freshdesk API에서 첨부파일은 보통 티켓 상세정보에 포함되어 있음
            # 별도 엔드포인트가 없으므로 티켓 상세에서 추출
            detail = await self.fetch_ticket_details(ticket_id)
            if detail and detail.get('raw_data', {}).get('attachments'):
                raw_attachments = detail['raw_data']['attachments']
                
                # 정규화 적용
                normalized_attachments = []
                for att in raw_attachments:
                    normalized_att = self.normalize_attachment(att)
                    normalized_attachments.append(normalized_att)
                
                return normalized_attachments
            
            return []
            
        except Exception as e:
            logger.error(f"티켓 {ticket_id} 첨부파일 정보 조회 실패: {e}")
            return []
    
    async def fetch_knowledge_base(
        self, 
        category_id: Optional[str] = None, 
        max_articles: Optional[int] = None
    ) -> List[Dict]:
        """
        지식베이스 문서 조회
        기존 optimized_fetcher.py의 fetch_knowledge_base_raw 로직 활용
        """
        all_articles = []
        articles_count = 0
        
        try:
            logger.info("지식베이스 수집 시작" + (f" (최대 {max_articles}개)" if max_articles else ""))
            
            # 1. 카테고리 목록 가져오기
            categories = []
            if category_id:
                # 특정 카테고리만 조회
                category = await self.fetch_with_retry(f"{self.base_url}/solutions/categories/{category_id}")
                if category:
                    categories = [category]
            else:
                # 전체 카테고리 조회
                categories = await self.fetch_with_retry(f"{self.base_url}/solutions/categories")
            
            logger.info(f"카테고리 {len(categories)}개 수신 완료")
            
            # 2. 각 카테고리별 폴더 및 아티클 수집
            for category in categories:
                cat_id = category["id"]
                cat_name = category.get("name", "Unknown")
                logger.info(f"카테고리 '{cat_name}' (ID: {cat_id}) 처리 중...")
                
                # 폴더 목록 가져오기
                folders = await self.fetch_with_retry(f"{self.base_url}/solutions/categories/{cat_id}/folders")
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
                            "per_page": self.per_page
                        }
                        
                        logger.info(f"폴더 '{folder_name}'의 아티클 페이지 {page} 요청 중...")
                        folder_articles = await self.fetch_with_retry(
                            f"{self.base_url}/solutions/folders/{folder_id}/articles", 
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
                        
                        # 정규화 적용
                        normalized_articles = []
                        for article in folder_articles:
                            normalized_article = self.normalize_kb_article(article)
                            normalized_articles.append(normalized_article)
                        
                        all_articles.extend(normalized_articles)
                        articles_count += len(normalized_articles)
                        logger.info(f"아티클 {len(normalized_articles)}개 추가 (현재까지 총 {articles_count}개)")
                        
                        # 최대 항목 수에 도달했으면 중단
                        if max_articles is not None and articles_count >= max_articles:
                            break
                        
                        # 이 배치가 불완전하면 마지막 페이지
                        if len(folder_articles) < self.per_page:
                            break
                            
                        page += 1
                        await asyncio.sleep(self.request_delay)
                    
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
    
    async def get_attachment_download_url(
        self, 
        attachment_id: str, 
        ticket_id: Optional[str] = None,
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        첨부파일 다운로드 URL 발급
        기존 attachments.py의 get_freshdesk_attachment_url 로직 활용
        """
        try:
            # 첨부파일이 티켓에 직접 연결된 경우
            if ticket_id and not conversation_id:
                # 티켓 상세 정보에서 첨부파일 URL 찾기
                ticket_url = f"{self.base_url}/tickets/{ticket_id}"
                logger.info(f"티켓 {ticket_id}에서 첨부파일 {attachment_id} 정보 조회 중...")
                
                response = await self.fetch_with_retry(ticket_url)
                
                # 티켓 첨부파일에서 해당 ID 찾기
                if "attachments" in response:
                    for attachment in response["attachments"]:
                        if str(attachment["id"]) == str(attachment_id):
                            return {
                                "id": attachment["id"],
                                "name": attachment["name"],
                                "content_type": attachment["content_type"],
                                "size": attachment["size"],
                                "download_url": attachment["attachment_url"],
                                "expires_at": "5분 후 만료",  # Freshdesk 기본값
                                "ticket_id": ticket_id,
                                "platform": self.platform,
                                "company_id": self.company_id
                            }
            
            # 대화에 첨부된 파일인 경우
            elif conversation_id:
                # 대화 정보에서 첨부파일 URL 찾기
                conv_url = f"{self.base_url}/conversations/{conversation_id}"
                logger.info(f"대화 {conversation_id}에서 첨부파일 {attachment_id} 정보 조회 중...")
                
                response = await self.fetch_with_retry(conv_url)
                
                # 대화 첨부파일에서 해당 ID 찾기
                if "attachments" in response:
                    for attachment in response["attachments"]:
                        if str(attachment["id"]) == str(attachment_id):
                            return {
                                "id": attachment["id"],
                                "name": attachment["name"],
                                "content_type": attachment["content_type"],
                                "size": attachment["size"],
                                "download_url": attachment["attachment_url"],
                                "expires_at": "5분 후 만료",
                                "conversation_id": conversation_id,
                                "ticket_id": ticket_id,
                                "platform": self.platform,
                                "company_id": self.company_id
                            }
            
            # 일반적인 접근: 티켓 목록에서 검색 (성능상 비추천, 마지막 수단)
            else:
                logger.warning(f"첨부파일 {attachment_id}에 대한 구체적인 위치 정보가 없어 전체 검색을 시도합니다")
                raise Exception("첨부파일 위치 정보(ticket_id 또는 conversation_id)가 필요합니다")
            
            # 첨부파일을 찾지 못한 경우
            raise Exception(f"첨부파일 {attachment_id}를 찾을 수 없습니다")
            
        except Exception as e:
            logger.error(f"첨부파일 URL 조회 중 오류: {e}")
            raise
    
    def _normalize_status(self, status: Any) -> str:
        """Freshdesk 상태를 공통 형식으로 정규화"""
        if status is None:
            return ""
        
        # Freshdesk 상태 코드를 문자열로 변환
        status_mapping = {
            2: "open",
            3: "pending", 
            4: "resolved",
            5: "closed"
        }
        
        if isinstance(status, int):
            return status_mapping.get(status, str(status))
        
        return str(status)
    
    def _normalize_priority(self, priority: Any) -> str:
        """Freshdesk 우선순위를 공통 형식으로 정규화"""
        if priority is None:
            return ""
        
        # Freshdesk 우선순위 코드를 문자열로 변환
        priority_mapping = {
            1: "low",
            2: "medium",
            3: "high", 
            4: "urgent"
        }
        
        if isinstance(priority, int):
            return priority_mapping.get(priority, str(priority))
        
        return str(priority)
    
    def _normalize_kb_status(self, status: Any) -> str:
        """Freshdesk KB 상태를 공통 형식으로 정규화"""
        if status is None:
            return ""
        
        # Freshdesk KB 상태 코드를 문자열로 변환
        status_mapping = {
            1: "draft",
            2: "published"
        }
        
        if isinstance(status, int):
            return status_mapping.get(status, str(status))
        
        return str(status)
