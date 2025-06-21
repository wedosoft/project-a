"""
Platform Adapter 추상화 기반 클래스
멀티플랫폼/멀티테넌트 지원을 위한 추상화 레이어
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class PlatformAdapter(ABC):
    """
    고객 서비스 플랫폼에 대한 추상화 인터페이스
    Freshdesk, Zendesk, ServiceNow 등 다양한 플랫폼을 통일된 방식으로 처리
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Args:
            config: 플랫폼별 설정 딕셔너리
                - platform: 플랫폼 이름 (freshdesk, zendesk 등)
                - company_id: 테넌트 식별자
                - domain: 플랫폼 도메인
                - api_key: API 키
                - 기타 플랫폼별 설정
        """
        self.platform = config.get("platform")
        self.company_id = config.get("company_id")
        self.domain = config.get("domain")
        self.api_key = config.get("api_key")
        self.config = config
        
        if not all([self.platform, self.company_id, self.domain, self.api_key]):
            raise ValueError("platform, company_id, domain, api_key는 필수 설정값입니다")
    
    @abstractmethod
    async def fetch_tickets_by_date_range(
        self, 
        start_date: str, 
        end_date: str, 
        page: int = 1, 
        per_page: int = 100
    ) -> List[Dict]:
        """
        날짜 범위로 티켓 목록 조회
        
        Args:
            start_date: 시작 날짜 (ISO 8601 형식)
            end_date: 종료 날짜 (ISO 8601 형식)
            page: 페이지 번호
            per_page: 페이지당 항목 수
            
        Returns:
            List[Dict]: 정규화된 티켓 목록
        """
        pass
    
    @abstractmethod
    async def fetch_ticket_details(self, ticket_id: str) -> Optional[Dict]:
        """
        티켓 상세정보 조회
        
        Args:
            ticket_id: 티켓 ID
            
        Returns:
            Optional[Dict]: 정규화된 티켓 상세정보
        """
        pass
    
    @abstractmethod
    async def fetch_conversations(self, ticket_id: str) -> List[Dict]:
        """
        티켓 대화내역 조회
        
        Args:
            ticket_id: 티켓 ID
            
        Returns:
            List[Dict]: 정규화된 대화내역 목록
        """
        pass
    
    @abstractmethod
    async def fetch_attachments(self, ticket_id: str) -> List[Dict]:
        """
        티켓 첨부파일 정보 조회
        
        Args:
            ticket_id: 티켓 ID
            
        Returns:
            List[Dict]: 정규화된 첨부파일 정보 목록
        """
        pass
    
    @abstractmethod
    async def fetch_knowledge_base(
        self, 
        category_id: Optional[str] = None, 
        max_articles: Optional[int] = None
    ) -> List[Dict]:
        """
        지식베이스 문서 조회
        
        Args:
            category_id: 카테고리 ID (선택사항)
            max_articles: 최대 문서 수 (선택사항)
            
        Returns:
            List[Dict]: 정규화된 지식베이스 문서 목록
        """
        pass
    
    @abstractmethod
    async def get_attachment_download_url(
        self, 
        attachment_id: str, 
        ticket_id: Optional[str] = None,
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        첨부파일 다운로드 URL 발급
        
        Args:
            attachment_id: 첨부파일 ID
            ticket_id: 티켓 ID (선택사항)
            conversation_id: 대화 ID (선택사항)
            
        Returns:
            Dict: 첨부파일 정보 및 다운로드 URL
        """
        pass
    
    def normalize_ticket(self, raw_ticket: Dict) -> Dict:
        """
        플랫폼별 티켓 데이터를 공통 형식으로 정규화
        
        Args:
            raw_ticket: 플랫폼별 원본 티켓 데이터
            
        Returns:
            Dict: 정규화된 티켓 데이터
        """
        # 기본 정규화 구조 - 서브클래스에서 오버라이드 가능
        return {
            "id": str(raw_ticket.get("id")),
            "platform": self.platform,
            "company_id": self.company_id,
            "subject": raw_ticket.get("subject", ""),
            "description": raw_ticket.get("description", ""),
            "status": self._normalize_status(raw_ticket.get("status")),
            "priority": self._normalize_priority(raw_ticket.get("priority")),
            "requester_id": str(raw_ticket.get("requester_id", "")),
            "assignee_id": str(raw_ticket.get("assignee_id", "")),
            "created_at": self._normalize_datetime(raw_ticket.get("created_at")),
            "updated_at": self._normalize_datetime(raw_ticket.get("updated_at")),
            "tags": raw_ticket.get("tags", []),
            "custom_fields": raw_ticket.get("custom_fields", {}),
            "raw_data": raw_ticket  # 원본 데이터 보존
        }
    
    def normalize_conversation(self, raw_conversation: Dict) -> Dict:
        """
        플랫폼별 대화 데이터를 공통 형식으로 정규화
        """
        return {
            "id": str(raw_conversation.get("id")),
            "platform": self.platform,
            "company_id": self.company_id,
            "ticket_id": str(raw_conversation.get("ticket_id", "")),
            "body": raw_conversation.get("body", ""),
            "body_text": raw_conversation.get("body_text", ""),
            "from_email": raw_conversation.get("from_email", ""),
            "to_emails": raw_conversation.get("to_emails", []),
            "user_id": str(raw_conversation.get("user_id", "")),
            "created_at": self._normalize_datetime(raw_conversation.get("created_at")),
            "updated_at": self._normalize_datetime(raw_conversation.get("updated_at")),
            "incoming": raw_conversation.get("incoming", False),
            "private": raw_conversation.get("private", False),
            "source": raw_conversation.get("source", ""),
            "attachments": raw_conversation.get("attachments", []),
            "raw_data": raw_conversation  # 원본 데이터 보존
        }
    
    def normalize_attachment(self, raw_attachment: Dict) -> Dict:
        """
        플랫폼별 첨부파일 데이터를 공통 형식으로 정규화
        """
        return {
            "id": str(raw_attachment.get("id")),
            "platform": self.platform,
            "company_id": self.company_id,
            "name": raw_attachment.get("name", ""),
            "content_type": raw_attachment.get("content_type", ""),
            "size": raw_attachment.get("size", 0),
            "created_at": self._normalize_datetime(raw_attachment.get("created_at")),
            "updated_at": self._normalize_datetime(raw_attachment.get("updated_at")),
            "raw_data": raw_attachment  # 원본 데이터 보존
        }
    
    def normalize_kb_article(self, raw_article: Dict) -> Dict:
        """
        플랫폼별 지식베이스 문서를 공통 형식으로 정규화
        """
        return {
            "id": str(raw_article.get("id")),
            "platform": self.platform,
            "company_id": self.company_id,
            "title": raw_article.get("title", ""),
            "description": raw_article.get("description", ""),
            "description_text": raw_article.get("description_text", ""),
            "status": self._normalize_kb_status(raw_article.get("status")),
            "category_id": str(raw_article.get("category_id", "")),
            "folder_id": str(raw_article.get("folder_id", "")),
            "author_id": str(raw_article.get("author_id", "")),
            "created_at": self._normalize_datetime(raw_article.get("created_at")),
            "updated_at": self._normalize_datetime(raw_article.get("updated_at")),
            "tags": raw_article.get("tags", []),
            "seo_data": raw_article.get("seo_data", {}),
            "raw_data": raw_article  # 원본 데이터 보존
        }
    
    def _normalize_status(self, status: Any) -> str:
        """플랫폼별 상태를 공통 형식으로 정규화"""
        # 기본 구현 - 서브클래스에서 플랫폼별로 오버라이드
        return str(status) if status is not None else ""
    
    def _normalize_priority(self, priority: Any) -> str:
        """플랫폼별 우선순위를 공통 형식으로 정규화"""
        # 기본 구현 - 서브클래스에서 플랫폼별로 오버라이드
        return str(priority) if priority is not None else ""
    
    def _normalize_kb_status(self, status: Any) -> str:
        """플랫폼별 KB 상태를 공통 형식으로 정규화"""
        # 기본 구현 - 서브클래스에서 플랫폼별로 오버라이드
        return str(status) if status is not None else ""
    
    def _normalize_datetime(self, dt_str: Any) -> str:
        """플랫폼별 날짜시간 형식을 ISO 8601로 정규화"""
        if not dt_str:
            return ""
        
        # 이미 문자열인 경우 그대로 반환 (대부분의 API가 ISO 8601 반환)
        if isinstance(dt_str, str):
            return dt_str
        
        # datetime 객체인 경우 ISO 형식으로 변환
        if hasattr(dt_str, 'isoformat'):
            return dt_str.isoformat()
        
        return str(dt_str)
