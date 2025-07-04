"""
데이터 병합 및 통합 객체 생성 모듈

티켓, 대화, 첨부파일 등 다양한 플랫폼 데이터를 
하나의 통합 객체로 병합하여 저장하는 기능을 제공합니다.
"""

import json
import hashlib
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class PlatformDataMerger:
    """멀티플랫폼 데이터 병합 클래스"""
    
    def __init__(self, platform: str, tenant_id: str):
        self.platform = platform
        self.tenant_id = tenant_id
    
    def merge_ticket_data(
        self,
        ticket: Dict[str, Any],
        conversations: Optional[List[Dict]] = None,
        attachments: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        티켓 원본, 대화 내역, 첨부파일을 하나의 문서로 병합
        
        Args:
            ticket: 티켓 원본 데이터
            conversations: 대화 내역 리스트 (선택사항)
            attachments: 첨부파일 메타데이터 리스트 (선택사항)
            
        Returns:
            병합된 티켓 문서
        """
        conversations = conversations or []
        attachments = attachments or []
        
        # 대화 내용을 텍스트로 병합
        conversation_text = ""
        if conversations:
            conversation_text = "\n\n".join([
                f"[{conv.get('created_at', '')}] {conv.get('body', '')}"
                for conv in conversations
                if conv.get('body')
            ])
        
        # 기본 병합 콘텐츠 생성
        merged_content_parts = []
        
        # 티켓 제목
        if ticket.get("subject"):
            merged_content_parts.append(f"제목: {ticket['subject']}")
        
        # 티켓 설명
        if ticket.get("description"):
            merged_content_parts.append(f"설명: {ticket['description']}")
        
        # 대화 내용
        if conversation_text:
            merged_content_parts.append(f"대화 내역:\n{conversation_text}")
        
        merged_content = "\n\n".join(merged_content_parts)
        
        # 통합 문서 구조 생성
        merged_document = {
            # 기본 식별 정보
            "original_id": str(ticket.get("id", "")),
            "platform": self.platform,
            "tenant_id": self.tenant_id,
            "doc_type": "ticket",
            
            # 콘텐츠 정보
            "subject": ticket.get("subject", ""),
            "description": ticket.get("description", ""),
            "merged_content": merged_content,
            
            # 상세 데이터
            "conversations": conversations,
            "attachments": [
                {
                    "attachment_id": str(att.get("id", "")),
                    "file_name": att.get("name", ""),
                    "content_type": att.get("content_type", ""),
                    "size": att.get("size", 0),
                    "url": att.get("attachment_url", ""),
                    "created_at": att.get("created_at", "")
                } for att in attachments
            ],
            
            # 메타데이터
            "metadata": {
                "status": ticket.get("status"),
                "priority": ticket.get("priority"),
                "created_at": ticket.get("created_at"),
                "updated_at": ticket.get("updated_at"),
                "tags": ticket.get("tags", []),
                "requester_id": ticket.get("requester_id"),
                "responder_id": ticket.get("responder_id"),
                "group_id": ticket.get("group_id"),
                "source": ticket.get("source"),
                "type": ticket.get("type")
            },
            
            # 시스템 정보
            "created_at_merged": datetime.now().isoformat(),
            "data_hash": "",  # 아래에서 생성
            "version": "1.0"
        }
        
        # 문서 해시 생성 (중복/변경 감지용)
        merged_document["data_hash"] = self.generate_document_hash(merged_document)
        
        return merged_document
    
    def merge_kb_article_data(
        self,
        article: Dict[str, Any],
        attachments: Optional[List[Dict]] = None
    ) -> Dict[str, Any]:
        """
        KB 아티클과 첨부파일을 하나의 문서로 병합
        
        Args:
            article: KB 아티클 원본 데이터
            attachments: 첨부파일 메타데이터 리스트 (선택사항)
            
        Returns:
            병합된 KB 문서
        """
        attachments = attachments or []
        
        # 기본 병합 콘텐츠 생성
        merged_content_parts = []
        
        # 아티클 제목
        if article.get("title"):
            merged_content_parts.append(f"제목: {article['title']}")
        
        # 아티클 내용
        if article.get("description"):
            merged_content_parts.append(f"내용: {article['description']}")
        
        merged_content = "\n\n".join(merged_content_parts)
        
        # 통합 문서 구조 생성
        merged_document = {
            # 기본 식별 정보
            "original_id": str(article.get("id", "")),
            "platform": self.platform,
            "tenant_id": self.tenant_id,
            "doc_type": "kb",
            
            # 콘텐츠 정보
            "title": article.get("title", ""),
            "description": article.get("description", ""),
            "merged_content": merged_content,
            
            # 상세 데이터
            "attachments": [
                {
                    "attachment_id": str(att.get("id", "")),
                    "file_name": att.get("name", ""),
                    "content_type": att.get("content_type", ""),
                    "size": att.get("size", 0),
                    "url": att.get("attachment_url", ""),
                    "created_at": att.get("created_at", "")
                } for att in attachments
            ],
            
            # 메타데이터
            "metadata": {
                "status": article.get("status"),
                "category_id": article.get("category_id"),
                "folder_id": article.get("folder_id"),
                "created_at": article.get("created_at"),
                "updated_at": article.get("updated_at"),
                "tags": article.get("tags", []),
                "agent_id": article.get("agent_id"),
                "views": article.get("views", 0),
                "thumbs_up": article.get("thumbs_up", 0),
                "thumbs_down": article.get("thumbs_down", 0)
            },
            
            # 시스템 정보
            "created_at_merged": datetime.now().isoformat(),
            "data_hash": "",  # 아래에서 생성
            "version": "1.0"
        }
        
        # 문서 해시 생성
        merged_document["data_hash"] = self.generate_document_hash(merged_document)
        
        return merged_document
    
    def generate_document_hash(self, document: Dict[str, Any]) -> str:
        """
        문서의 해시값 생성 (중복/변경 감지용)
        
        Args:
            document: 해시를 생성할 문서
            
        Returns:
            SHA-256 해시값
        """
        # 해시 계산에서 제외할 필드들 (시간 관련, 시스템 필드)
        exclude_fields = {
            "created_at_merged", "data_hash", "version"
        }
        
        # 해시 계산용 딕셔너리 생성
        hash_dict = {
            k: v for k, v in document.items() 
            if k not in exclude_fields
        }
        
        # JSON 문자열로 변환 후 해시 생성
        doc_str = json.dumps(hash_dict, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(doc_str.encode('utf-8')).hexdigest()
    
    def validate_merged_document(self, document: Dict[str, Any]) -> bool:
        """
        병합된 문서의 유효성 검증
        
        Args:
            document: 검증할 문서
            
        Returns:
            유효성 여부
        """
        required_fields = [
            "original_id", "platform", "tenant_id", "doc_type",
            "merged_content", "metadata", "data_hash"
        ]
        
        for field in required_fields:
            if field not in document:
                logger.error(f"필수 필드 누락: {field}")
                return False
        
        # 플랫폼/테넌트 ID 검증
        if document["platform"] != self.platform:
            logger.error(f"플랫폼 불일치: {document['platform']} != {self.platform}")
            return False
            
        if document["tenant_id"] != self.tenant_id:
            logger.error(f"테넌트 ID 불일치: {document['tenant_id']} != {self.tenant_id}")
            return False
        
        # 문서 타입 검증
        if document["doc_type"] not in ["ticket", "kb"]:
            logger.error(f"지원하지 않는 문서 타입: {document['doc_type']}")
            return False
        
        return True


class DataStorage:
    """데이터 저장소 추상화 클래스"""
    
    def __init__(self, storage_type: str = "file", base_path: Optional[Path] = None):
        self.storage_type = storage_type
        self.base_path = base_path or Path("data/merged")
        
        if storage_type == "file":
            self.base_path.mkdir(parents=True, exist_ok=True)
    
    async def save_merged_document(
        self,
        platform: str,
        tenant_id: str,
        document: Dict[str, Any],
        doc_type: str
    ) -> str:
        """
        병합된 문서 저장
        
        Args:
            platform: 플랫폼 이름
            tenant_id: 테넌트 ID
            document: 저장할 문서
            doc_type: 문서 타입 (ticket/kb)
            
        Returns:
            저장된 문서 ID 또는 경로
        """
        if self.storage_type == "file":
            return await self._save_to_file(platform, tenant_id, document, doc_type)
        elif self.storage_type == "database":
            return await self._save_to_database(platform, tenant_id, document, doc_type)
        else:
            raise ValueError(f"지원하지 않는 저장소 타입: {self.storage_type}")
    
    async def _save_to_file(
        self,
        platform: str,
        tenant_id: str,
        document: Dict[str, Any],
        doc_type: str
    ) -> str:
        """파일 시스템에 저장"""
        # 디렉토리 구조: data/merged/{platform}/{tenant_id}/{doc_type}/
        doc_dir = self.base_path / platform / tenant_id / doc_type
        doc_dir.mkdir(parents=True, exist_ok=True)
        
        # 파일명: {original_id}_{timestamp}.json
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{document['original_id']}_{timestamp}.json"
        filepath = doc_dir / filename
        
        # JSON 파일로 저장
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(document, f, ensure_ascii=False, indent=2)
        
        logger.debug(f"문서 저장 완료: {filepath}")
        return str(filepath)
    
    async def _save_to_database(
        self,
        platform: str,
        tenant_id: str,
        document: Dict[str, Any],
        doc_type: str
    ) -> str:
        """데이터베이스에 저장 (PostgreSQL JSONB)"""
        # TODO: 데이터베이스 저장 로직 구현
        # 현재는 NotImplementedError 발생
        raise NotImplementedError("데이터베이스 저장 기능은 아직 구현되지 않았습니다.")
    
    async def load_merged_documents(
        self,
        platform: str,
        tenant_id: str,
        doc_type: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        병합된 문서 로드
        
        Args:
            platform: 플랫폼 이름
            tenant_id: 테넌트 ID
            doc_type: 문서 타입 필터 (선택사항)
            limit: 최대 로드 개수 (선택사항)
            
        Returns:
            문서 리스트
        """
        if self.storage_type == "file":
            return await self._load_from_file(platform, tenant_id, doc_type, limit)
        elif self.storage_type == "database":
            return await self._load_from_database(platform, tenant_id, doc_type, limit)
        else:
            raise ValueError(f"지원하지 않는 저장소 타입: {self.storage_type}")
    
    async def _load_from_file(
        self,
        platform: str,
        tenant_id: str,
        doc_type: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """파일 시스템에서 로드"""
        documents = []
        
        if doc_type:
            # 특정 문서 타입만 로드
            doc_dirs = [self.base_path / platform / tenant_id / doc_type]
        else:
            # 모든 문서 타입 로드
            company_dir = self.base_path / platform / tenant_id
            if not company_dir.exists():
                return documents
            doc_dirs = [d for d in company_dir.iterdir() if d.is_dir()]
        
        loaded_count = 0
        for doc_dir in doc_dirs:
            if not doc_dir.exists():
                continue
                
            for json_file in doc_dir.glob("*.json"):
                if limit and loaded_count >= limit:
                    break
                    
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        document = json.load(f)
                        documents.append(document)
                        loaded_count += 1
                except Exception as e:
                    logger.error(f"문서 로드 실패 {json_file}: {e}")
                    continue
        
        return documents
    
    async def _load_from_database(
        self,
        platform: str,
        tenant_id: str,
        doc_type: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """데이터베이스에서 로드"""
        # TODO: 데이터베이스 로드 로직 구현
        raise NotImplementedError("데이터베이스 로드 기능은 아직 구현되지 않았습니다.")
