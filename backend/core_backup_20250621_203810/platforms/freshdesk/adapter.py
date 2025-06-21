# -*- coding: utf-8 -*-
"""
Freshdesk 플랫폼 어댑터 구현
기존 optimized_fetcher.py의 로직을 플랫폼 어댑터 패턴으로 리팩토링
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any
import httpx
from datetime import datetime

from ..factory import PlatformAdapter

logger = logging.getLogger(__name__)


class FreshdeskAdapter(PlatformAdapter):
    """
    Freshdesk API를 위한 플랫폼 어댑터
    기존 optimized_fetcher.py의 Freshdesk 로직을 재사용하면서 추상화 적용
    """
    
    def __init__(self, config: Dict[str, Any]):
        # 기본 설정 값 추출
        self.domain = config.get("domain")
        self.api_key = config.get("api_key")
        self.company_id = config.get("company_id")
        self.platform = "freshdesk"
        
        if not all([self.domain, self.api_key, self.company_id]):
            raise ValueError("Freshdesk 설정에 domain, api_key, company_id가 필요합니다")
        
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
    
    def get_platform_name(self) -> str:
        """플랫폼 이름 반환"""
        return "freshdesk"
    
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
    
    async def fetch_tickets(self, since_date: str = None, include_attachments: bool = True) -> list:
        """티켓 데이터 수집 (PlatformAdapter 인터페이스 구현)"""
        all_tickets = []
        
        try:
            # 페이지네이션으로 티켓 수집
            page = 1
            while True:
                params = {
                    "page": page,
                    "per_page": self.per_page,
                    "order_by": "updated_at",
                    "order_type": "asc"
                }
                
                if since_date:
                    params["updated_since"] = since_date
                
                batch_tickets = await self.fetch_with_retry(f"{self.base_url}/tickets", params)
                
                if not batch_tickets:
                    break
                
                # 정규화 적용
                normalized_tickets = []
                for ticket in batch_tickets:
                    normalized_ticket = self._normalize_ticket_data(ticket)
                    
                    # 첨부파일 정보 추가
                    if include_attachments and ticket.get('attachments'):
                        for att in ticket['attachments']:
                            normalized_att = self._normalize_attachment_data(att)
                            normalized_ticket.setdefault('attachments', []).append(normalized_att)
                    
                    normalized_tickets.append(normalized_ticket)
                
                all_tickets.extend(normalized_tickets)
                
                # 이 배치가 불완전하면 마지막 페이지
                if len(batch_tickets) < self.per_page:
                    break
                
                page += 1
                await asyncio.sleep(self.request_delay)
            
            logger.info(f"Freshdesk 티켓 수집 완료: {len(all_tickets)}개")
            return all_tickets
            
        except Exception as e:
            logger.error(f"Freshdesk 티켓 수집 실패: {e}")
            raise
    
    async def fetch_kb_articles(self, since_date: str = None) -> list:
        """KB 아티클 수집 (PlatformAdapter 인터페이스 구현)"""
        all_articles = []
        
        try:
            logger.info("Freshdesk 지식베이스 수집 시작")
            
            # 1. 카테고리 목록 가져오기
            categories = await self.fetch_with_retry(f"{self.base_url}/solutions/categories")
            logger.info(f"카테고리 {len(categories)}개 수신 완료")
            
            # 2. 각 카테고리별 폴더 및 아티클 수집
            for category in categories:
                cat_id = category["id"]
                cat_name = category.get("name", "Unknown")
                
                # 폴더 목록 가져오기
                folders = await self.fetch_with_retry(f"{self.base_url}/solutions/categories/{cat_id}/folders")
                
                # 3. 각 폴더별 아티클 수집
                for folder in folders:
                    folder_id = folder["id"]
                    folder_name = folder.get("name", "Unknown")
                    
                    # 폴더별 페이지네이션 처리
                    page = 1
                    while True:
                        params = {
                            "page": page,
                            "per_page": self.per_page
                        }
                        
                        folder_articles = await self.fetch_with_retry(
                            f"{self.base_url}/solutions/folders/{folder_id}/articles", 
                            params
                        )
                        
                        if not folder_articles:
                            break
                        
                        # 카테고리 및 폴더 정보 추가
                        for article in folder_articles:
                            article["category_id"] = cat_id
                            article["category_name"] = cat_name
                            article["folder_id"] = folder_id
                            article["folder_name"] = folder_name
                        
                        # 정규화 적용
                        normalized_articles = []
                        for article in folder_articles:
                            # since_date 필터링
                            if since_date and article.get('updated_at', '') < since_date:
                                continue
                                
                            normalized_article = self._normalize_kb_data(article)
                            normalized_articles.append(normalized_article)
                        
                        all_articles.extend(normalized_articles)
                        
                        # 이 배치가 불완전하면 마지막 페이지
                        if len(folder_articles) < self.per_page:
                            break
                            
                        page += 1
                        await asyncio.sleep(self.request_delay)
            
            logger.info(f"Freshdesk 지식베이스 수집 완료: {len(all_articles)}개")
            return all_articles
            
        except Exception as e:
            logger.error(f"Freshdesk 지식베이스 수집 실패: {e}")
            raise
    
    async def get_attachment_url(self, attachment_id: str, **kwargs) -> str:
        """첨부파일 다운로드 URL 생성 (PlatformAdapter 인터페이스 구현)"""
        ticket_id = kwargs.get('ticket_id')
        conversation_id = kwargs.get('conversation_id')
        
        try:
            # 첨부파일이 티켓에 직접 연결된 경우
            if ticket_id and not conversation_id:
                response = await self.fetch_with_retry(f"{self.base_url}/tickets/{ticket_id}")
                
                # 티켓 첨부파일에서 해당 ID 찾기
                if "attachments" in response:
                    for attachment in response["attachments"]:
                        if str(attachment["id"]) == str(attachment_id):
                            return attachment["attachment_url"]
            
            # 대화에 첨부된 파일인 경우
            elif conversation_id:
                response = await self.fetch_with_retry(f"{self.base_url}/conversations/{conversation_id}")
                
                # 대화 첨부파일에서 해당 ID 찾기
                if "attachments" in response:
                    for attachment in response["attachments"]:
                        if str(attachment["id"]) == str(attachment_id):
                            return attachment["attachment_url"]
            
            raise Exception(f"첨부파일 {attachment_id}를 찾을 수 없습니다")
            
        except Exception as e:
            logger.error(f"첨부파일 URL 조회 중 오류: {e}")
            raise
    
    def _normalize_ticket_data(self, ticket: Dict) -> Dict:
        """티켓 데이터 정규화"""
        return {
            "id": str(ticket.get("id", "")),
            "subject": ticket.get("subject", ""),
            "description": ticket.get("description", ""),
            "status": self._normalize_status(ticket.get("status")),
            "priority": self._normalize_priority(ticket.get("priority")),
            "requester_id": str(ticket.get("requester_id", "")),
            "responder_id": str(ticket.get("responder_id", "")),
            "group_id": str(ticket.get("group_id", "")),
            "company_id": str(ticket.get("company_id", "")),
            "created_at": ticket.get("created_at", ""),
            "updated_at": ticket.get("updated_at", ""),
            "due_by": ticket.get("due_by", ""),
            "fr_due_by": ticket.get("fr_due_by", ""),
            "type": ticket.get("type", ""),
            "source": ticket.get("source", ""),
            "tags": ticket.get("tags", []),
            "platform": self.platform,
            "platform_company_id": self.company_id,
            "doc_type": "ticket",
            "raw_data": ticket
        }
    
    def _normalize_kb_data(self, article: Dict) -> Dict:
        """KB 아티클 데이터 정규화"""
        return {
            "id": str(article.get("id", "")),
            "title": article.get("title", ""),
            "description": article.get("description", ""),
            "body": article.get("description_text", ""),  # Freshdesk는 description_text 필드 사용
            "status": self._normalize_kb_status(article.get("status")),
            "category_id": str(article.get("category_id", "")),
            "category_name": article.get("category_name", ""),
            "folder_id": str(article.get("folder_id", "")),
            "folder_name": article.get("folder_name", ""),
            "created_at": article.get("created_at", ""),
            "updated_at": article.get("updated_at", ""),
            "tags": article.get("tags", []),
            "platform": self.platform,
            "platform_company_id": self.company_id,
            "doc_type": "kb",
            "raw_data": article
        }
    
    def _normalize_attachment_data(self, attachment: Dict) -> Dict:
        """첨부파일 데이터 정규화"""
        return {
            "id": str(attachment.get("id", "")),
            "name": attachment.get("name", ""),
            "content_type": attachment.get("content_type", ""),
            "size": attachment.get("size", 0),
            "attachment_url": attachment.get("attachment_url", ""),
            "platform": self.platform,
            "platform_company_id": self.company_id,
            "raw_data": attachment
        }
    
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
