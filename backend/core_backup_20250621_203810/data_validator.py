# -*- coding: utf-8 -*-
"""
데이터 검증 모듈

문서 데이터의 무결성을 검증하고 자동으로 보정하는 함수들을 제공합니다.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

from .constants import DocType, SystemConfig
from .doc_id_utils import DocIdUtils

logger = logging.getLogger(__name__)


class DocumentValidator:
    """문서 데이터 검증 클래스"""
    
    @staticmethod
    def validate_document_metadata(doc: Dict[str, Any], 
                                 auto_fix: bool = True,
                                 company_id: Optional[str] = None) -> Tuple[Dict[str, Any], List[str]]:
        """
        문서 메타데이터 검증 및 자동 보정
        
        Args:
            doc: 검증할 문서 딕셔너리
            auto_fix: 자동 보정 여부
            company_id: 회사 ID (검증용)
            
        Returns:
            (보정된_문서, 경고_메시지_리스트) 튜플
        """
        warnings = []
        fixed_doc = doc.copy()
        
        # 1. 기본 필드 검증
        doc_id = fixed_doc.get('id')
        if not doc_id:
            if auto_fix:
                # 임시 ID 생성
                fixed_doc['id'] = f"temp_{id(doc)}"
                warnings.append("문서에 id가 없어 임시 ID를 생성했습니다.")
            else:
                raise ValueError("문서에 id가 없습니다.")
        
        # 2. doc_id 검증 및 정규화
        try:
            normalized_id = DocIdUtils.validate_and_normalize_doc_id(fixed_doc['id'])
            fixed_doc['id'] = normalized_id
        except ValueError as e:
            warnings.append(f"doc_id 정규화 실패: {e}")
        
        # 3. metadata 필드 확인
        if 'metadata' not in fixed_doc:
            fixed_doc['metadata'] = {}
            warnings.append("metadata 필드가 없어 빈 딕셔너리로 초기화했습니다.")
        
        metadata = fixed_doc['metadata']
        
        # 4. doc_type 검증 및 자동 보정
        if not metadata.get('doc_type'):
            if auto_fix:
                try:
                    # doc_id에서 자동 추출
                    doc_type = DocIdUtils.parse_doc_id(fixed_doc['id'])['doc_type']
                    if doc_type:
                        metadata['doc_type'] = doc_type
                        warnings.append(f"doc_id에서 doc_type '{doc_type}'을 자동 추출했습니다.")
                    else:
                        # 기본값 설정
                        metadata['doc_type'] = DocType.TICKET.value
                        warnings.append(f"doc_type을 기본값 '{DocType.TICKET.value}'로 설정했습니다.")
                except Exception as e:
                    metadata['doc_type'] = DocType.TICKET.value
                    warnings.append(f"doc_type 자동 추출 실패, 기본값 설정: {e}")
            else:
                raise ValueError("doc_type이 없습니다.")
        
        # 5. company_id 검증
        if company_id and metadata.get('company_id') != company_id:
            if auto_fix:
                metadata['company_id'] = company_id
                warnings.append(f"company_id를 '{company_id}'로 설정했습니다.")
        
        # 6. 텍스트 내용 검증
        if not fixed_doc.get('text') or not fixed_doc['text'].strip():
            warnings.append("문서에 텍스트 내용이 없습니다.")
        
        # 7. 타임스탬프 필드 확인
        if 'created_at' not in metadata:
            from datetime import datetime
            metadata['created_at'] = datetime.now().isoformat()
            warnings.append("created_at 필드를 현재 시간으로 설정했습니다.")
        
        return fixed_doc, warnings
    
    @staticmethod
    def validate_document_batch(docs: List[Dict[str, Any]], 
                              company_id: Optional[str] = None,
                              auto_fix: bool = True,
                              stop_on_error: bool = False) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        문서 배치 검증
        
        Args:
            docs: 검증할 문서 리스트
            company_id: 회사 ID
            auto_fix: 자동 보정 여부
            stop_on_error: 오류 시 중단 여부
            
        Returns:
            (검증된_문서_리스트, 검증_결과_요약) 튜플
        """
        validated_docs = []
        validation_summary = {
            'total_docs': len(docs),
            'successful': 0,
            'warnings': 0,
            'errors': 0,
            'all_warnings': [],
            'all_errors': []
        }
        
        for i, doc in enumerate(docs):
            try:
                validated_doc, warnings = DocumentValidator.validate_document_metadata(
                    doc, auto_fix=auto_fix, company_id=company_id
                )
                validated_docs.append(validated_doc)
                validation_summary['successful'] += 1
                
                if warnings:
                    validation_summary['warnings'] += 1
                    validation_summary['all_warnings'].extend([
                        f"문서 {i}: {warning}" for warning in warnings
                    ])
                
            except Exception as e:
                error_msg = f"문서 {i} 검증 실패: {e}"
                validation_summary['errors'] += 1
                validation_summary['all_errors'].append(error_msg)
                logger.error(error_msg)
                
                if stop_on_error:
                    raise
                
                # 오류가 있어도 원본 문서 유지 (auto_fix가 False인 경우)
                if not auto_fix:
                    validated_docs.append(doc)
        
        return validated_docs, validation_summary
    
    @staticmethod
    def check_duplicate_doc_ids(docs: List[Dict[str, Any]]) -> Dict[str, List[int]]:
        """
        중복 doc_id 검사
        
        Args:
            docs: 검사할 문서 리스트
            
        Returns:
            중복된 doc_id와 해당 인덱스들의 딕셔너리
        """
        doc_id_map = {}
        duplicates = {}
        
        for i, doc in enumerate(docs):
            doc_id = doc.get('id')
            if doc_id:
                if doc_id not in doc_id_map:
                    doc_id_map[doc_id] = []
                doc_id_map[doc_id].append(i)
        
        # 중복 찾기
        for doc_id, indices in doc_id_map.items():
            if len(indices) > 1:
                duplicates[doc_id] = indices
        
        return duplicates
    
    @staticmethod
    def sanitize_text_content(text: str) -> str:
        """
        텍스트 내용 정제
        
        Args:
            text: 정제할 텍스트
            
        Returns:
            정제된 텍스트
        """
        if not text:
            return ""
        
        # 공백 정리
        text = text.strip()
        
        # 연속된 공백 제거
        import re
        text = re.sub(r'\s+', ' ', text)
        
        # 특수 문자 제거 (필요에 따라 조정)
        # text = re.sub(r'[^\w\s가-힣]', '', text)
        
        return text
    
    @staticmethod
    def validate_company_isolation(docs: List[Dict[str, Any]], expected_company_id: str) -> List[str]:
        """
        회사별 데이터 격리 검증
        
        Args:
            docs: 검증할 문서 리스트
            expected_company_id: 기대되는 회사 ID
            
        Returns:
            위반 사항 리스트
        """
        violations = []
        
        for i, doc in enumerate(docs):
            metadata = doc.get('metadata', {})
            doc_company_id = metadata.get('company_id')
            
            if doc_company_id and doc_company_id != expected_company_id:
                violations.append(
                    f"문서 {i} (id: {doc.get('id')}): "
                    f"잘못된 company_id '{doc_company_id}', 기대값: '{expected_company_id}'"
                )
        
        return violations
