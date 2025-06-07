# -*- coding: utf-8 -*-
"""
Doc ID 유틸리티 모듈

doc_id 생성, 검증, 변환 등의 유틸리티 함수를 제공합니다.
"""

import logging
from typing import Any, Dict, Optional, Tuple

from .constants import ChunkConstants, DocIdPrefix, DocType

logger = logging.getLogger(__name__)


class DocIdUtils:
    """Doc ID 관련 유틸리티 클래스"""
    
    @staticmethod
    def validate_and_normalize_doc_id(doc_id: str) -> str:
        """
        doc_id 검증 및 정규화
        
        Args:
            doc_id: 검증할 doc_id
            
        Returns:
            정규화된 doc_id
            
        Raises:
            ValueError: 유효하지 않은 doc_id인 경우
        """
        if not doc_id or not isinstance(doc_id, str):
            raise ValueError(f"doc_id는 비어있지 않은 문자열이어야 합니다: {doc_id}")
        
        # 공백 제거
        doc_id = doc_id.strip()
        
        # 접두어가 없는 경우 경고 로그
        if not DocIdPrefix.is_valid_doc_id(doc_id):
            logger.warning(f"doc_id '{doc_id}'에 유효한 접두어가 없습니다.")
        
        return doc_id
    
    @staticmethod
    def parse_doc_id(doc_id: str) -> Dict[str, Any]:
        """
        doc_id를 파싱하여 상세 정보 반환
        
        Args:
            doc_id: 파싱할 doc_id
            
        Returns:
            파싱된 정보를 담은 딕셔너리
            {
                'original_doc_id': str,
                'doc_type': str,
                'original_id': str,
                'is_chunk': bool,
                'chunk_index': Optional[int],
                'base_doc_id': Optional[str]
            }
        """
        result = {
            'original_doc_id': doc_id,
            'doc_type': None,
            'original_id': None,
            'is_chunk': False,
            'chunk_index': None,
            'base_doc_id': None
        }
        
        try:
            # 청크인지 확인
            if ChunkConstants.is_chunk_id(doc_id):
                result['is_chunk'] = True
                base_doc_id = ChunkConstants.extract_base_doc_id(doc_id)
                result['base_doc_id'] = base_doc_id
                
                # 청크 인덱스 추출
                chunk_part = doc_id.split(ChunkConstants.SEPARATOR)[1]
                try:
                    result['chunk_index'] = int(chunk_part)
                except ValueError:
                    logger.warning(f"청크 인덱스를 파싱할 수 없습니다: {chunk_part}")
                
                # 기본 doc_id로 타입 추출
                doc_id_for_type = base_doc_id
            else:
                doc_id_for_type = doc_id
            
            # doc_type 추출
            try:
                result['doc_type'] = DocIdPrefix.extract_doc_type(doc_id_for_type)
                result['original_id'] = DocIdPrefix.extract_original_id(doc_id_for_type)
            except ValueError:
                logger.warning(f"doc_id에서 타입을 추출할 수 없습니다: {doc_id_for_type}")
                result['original_id'] = doc_id_for_type
                
        except Exception as e:
            logger.error(f"doc_id 파싱 중 오류 발생: {e}")
        
        return result
    
    @staticmethod
    def create_doc_id_with_validation(doc_type: str, original_id: str) -> str:
        """
        검증과 함께 doc_id 생성
        
        Args:
            doc_type: 문서 타입
            original_id: 원본 ID
            
        Returns:
            생성된 doc_id
            
        Raises:
            ValueError: 유효하지 않은 파라미터인 경우
        """
        if not doc_type or not original_id:
            raise ValueError("doc_type과 original_id는 필수입니다.")
        
        # doc_type 검증
        valid_types = {dtype.value for dtype in DocType}
        if doc_type not in valid_types:
            raise ValueError(f"지원하지 않는 doc_type: {doc_type}. 지원 타입: {valid_types}")
        
        # original_id 검증 (숫자 또는 문자열)
        original_id = str(original_id).strip()
        if not original_id:
            raise ValueError("original_id는 비어있을 수 없습니다.")
        
        return DocIdPrefix.create_doc_id(doc_type, original_id)
    
    @staticmethod
    def migrate_legacy_doc_id(doc_id: str, fallback_doc_type: Optional[str] = None) -> Tuple[str, str]:
        """
        레거시 doc_id를 새로운 형식으로 마이그레이션
        
        Args:
            doc_id: 마이그레이션할 doc_id
            fallback_doc_type: 접두어가 없을 때 사용할 기본 타입
            
        Returns:
            (새로운_doc_id, 추출된_doc_type) 튜플
        """
        # 이미 유효한 형식인 경우
        if DocIdPrefix.is_valid_doc_id(doc_id):
            doc_type = DocIdPrefix.extract_doc_type(doc_id)
            return doc_id, doc_type
        
        # 접두어가 없는 경우
        if fallback_doc_type:
            new_doc_id = DocIdPrefix.create_doc_id(fallback_doc_type, doc_id)
            logger.info(f"레거시 doc_id '{doc_id}'를 '{new_doc_id}'로 마이그레이션했습니다.")
            return new_doc_id, fallback_doc_type
        
        # 기본값으로 ticket 타입 사용
        default_type = DocType.TICKET.value
        new_doc_id = DocIdPrefix.create_doc_id(default_type, doc_id)
        logger.warning(f"레거시 doc_id '{doc_id}'를 기본 타입 '{default_type}'으로 마이그레이션했습니다.")
        return new_doc_id, default_type
    
    @staticmethod
    def batch_normalize_doc_ids(doc_ids: List[str]) -> List[str]:
        """
        doc_id 리스트를 일괄 정규화
        
        Args:
            doc_ids: 정규화할 doc_id 리스트
            
        Returns:
            정규화된 doc_id 리스트
        """
        normalized = []
        for doc_id in doc_ids:
            try:
                normalized_id = DocIdUtils.validate_and_normalize_doc_id(doc_id)
                normalized.append(normalized_id)
            except ValueError as e:
                logger.error(f"doc_id 정규화 실패: {e}")
                # 오류가 있어도 원본 ID를 유지
                normalized.append(doc_id)
        
        return normalized
    
    @staticmethod
    def extract_company_and_doc_info(doc_id: str, company_id: str) -> Dict[str, Any]:
        """
        doc_id와 company_id를 조합하여 전체 문서 정보 추출
        
        Args:
            doc_id: 문서 ID
            company_id: 회사 ID
            
        Returns:
            전체 문서 정보
        """
        doc_info = DocIdUtils.parse_doc_id(doc_id)
        doc_info['company_id'] = company_id
        doc_info['full_document_key'] = f"{company_id}:{doc_id}"
        
        return doc_info
