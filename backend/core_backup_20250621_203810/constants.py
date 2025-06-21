# -*- coding: utf-8 -*-
"""
시스템 전체에서 사용하는 상수 정의

doc_id 접두어 패턴과 관련 설정을 중앙에서 관리합니다.
"""

import os
from enum import Enum
from typing import Dict, Set


class DocType(Enum):
    """문서 타입 열거형"""
    TICKET = "ticket"
    KNOWLEDGE_BASE = "kb"
    ATTACHMENT = "attachment"
    IMAGE = "image"


class DocIdPrefix:
    """doc_id 접두어 패턴 관리 클래스"""
    
    # 접두어 정의
    TICKET = "ticket-"
    KB = "kb-"
    ATTACHMENT = "att-"
    IMAGE = "img-"
    
    # 접두어와 타입 매핑
    PREFIX_TO_TYPE: Dict[str, str] = {
        TICKET: DocType.TICKET.value,
        KB: DocType.KNOWLEDGE_BASE.value,
        ATTACHMENT: DocType.ATTACHMENT.value,
        IMAGE: DocType.IMAGE.value,
    }
    
    # 타입과 접두어 매핑 (역방향)
    TYPE_TO_PREFIX: Dict[str, str] = {
        DocType.TICKET.value: TICKET,
        DocType.KNOWLEDGE_BASE.value: KB,
        DocType.ATTACHMENT.value: ATTACHMENT,
        DocType.IMAGE.value: IMAGE,
    }
    
    @classmethod
    def get_all_prefixes(cls) -> Set[str]:
        """모든 접두어 반환"""
        return set(cls.PREFIX_TO_TYPE.keys())
    
    @classmethod
    def extract_doc_type(cls, doc_id: str) -> str:
        """doc_id에서 doc_type 추출"""
        for prefix, doc_type in cls.PREFIX_TO_TYPE.items():
            if doc_id.startswith(prefix):
                return doc_type
        raise ValueError(f"알 수 없는 doc_id 접두어: {doc_id}")
    
    @classmethod
    def extract_original_id(cls, doc_id: str) -> str:
        """doc_id에서 원본 ID 추출 (접두어 제거)"""
        for prefix in cls.PREFIX_TO_TYPE.keys():
            if doc_id.startswith(prefix):
                return doc_id[len(prefix):]
        return doc_id  # 접두어가 없으면 그대로 반환
    
    @classmethod
    def create_doc_id(cls, doc_type: str, original_id: str) -> str:
        """doc_type과 원본 ID로 doc_id 생성"""
        if doc_type not in cls.TYPE_TO_PREFIX:
            raise ValueError(f"지원하지 않는 doc_type: {doc_type}")
        prefix = cls.TYPE_TO_PREFIX[doc_type]
        return f"{prefix}{original_id}"
    
    @classmethod
    def is_valid_doc_id(cls, doc_id: str) -> bool:
        """유효한 doc_id인지 검증"""
        return any(doc_id.startswith(prefix) for prefix in cls.PREFIX_TO_TYPE.keys())


# 청크 관련 상수
class ChunkConstants:
    """청크 처리 관련 상수"""
    SEPARATOR = "_chunk_"
    MAX_CHUNK_INDEX = 9999
    
    @classmethod
    def create_chunk_id(cls, doc_id: str, chunk_index: int) -> str:
        """청크 ID 생성"""
        return f"{doc_id}{cls.SEPARATOR}{chunk_index}"
    
    @classmethod
    def extract_base_doc_id(cls, chunk_id: str) -> str:
        """청크 ID에서 기본 doc_id 추출"""
        if cls.SEPARATOR in chunk_id:
            return chunk_id.split(cls.SEPARATOR)[0]
        return chunk_id
    
    @classmethod
    def is_chunk_id(cls, doc_id: str) -> bool:
        """청크 ID인지 확인"""
        return cls.SEPARATOR in doc_id


# 시스템 전체 설정
class SystemConfig:
    """시스템 전체 설정"""
    
    # 기본 company_id
    DEFAULT_COMPANY_ID = os.getenv("COMPANY_ID", "example-company")
    
    # 벡터 DB 컬렉션명 패턴
    VECTOR_COLLECTION_PATTERN = "{company_id}_documents"
    
    # 지원하는 문서 타입들
    SUPPORTED_DOC_TYPES = {
        DocType.TICKET.value,
        DocType.KNOWLEDGE_BASE.value,
        DocType.ATTACHMENT.value,
        DocType.IMAGE.value,
    }
