"""
Tenant Metadata 정규화 및 확장 모듈

tenant_metadata의 비정상 값 방지, 정규화, 그리고 확장 필드 처리를 담당합니다.
"""

import json
import logging
from typing import Dict, Any, Optional, List, Union
from datetime import datetime

logger = logging.getLogger(__name__)

class TenantMetadataNormalizer:
    """Tenant Metadata 정규화 및 확장 처리 클래스"""
    
    # 기본 스키마 정의
    DEFAULT_SCHEMA = {
        # Freshdesk API 원본 필드들
        "id": None,                   # 티켓 ID (숫자, API 원본)
        "original_id": None,          # 벡터DB용 ID (문자열, 시스템 처리용)
        "subject": "",                # 티켓 제목
        "description": "",            # 티켓 설명
        "description_text": "",       # 플레인 텍스트 설명
        "status": 2,                  # 숫자 ID (2=Open, 3=Pending, 4=Resolved, 5=Closed, 6=Spam)
        "priority": 1,                # 우선순위 (1=Low, 2=Medium, 3=High, 4=Urgent)
        "requester_id": None,         # 요청자 ID
        "created_at": None,           # 생성 시간
        "updated_at": None,           # 수정 시간
        
        # 파생 계산 필드들
        "has_conversations": False,
        "has_attachments": False,
        "conversation_count": 0,
        "attachment_count": 0,
        "attachments": [],
        
        # Phase 1 확장 필드
        "company_name": "",           # 고객사명
        "agent_name": "",             # 담당자명
        "customer_email": "",         # 고객 이메일
        "ticket_category": "",        # 티켓 카테고리
        "complexity_level": "medium", # 복잡도 (low/medium/high)
        "estimated_resolution_time": None,  # 예상 해결 시간
        "department": "",             # 부서
        "product_version": "",        # 제품 버전
        
        # 첨부파일 메타데이터 확장
        "attachment_types": [],       # 첨부파일 유형 목록
        "has_image_attachments": False,  # 이미지 첨부파일 여부
        "has_document_attachments": False,  # 문서 첨부파일 여부
        "large_attachments": False,   # 대용량 첨부파일 여부 (5MB+)
        
        # AI 처리 이력
        "ai_summary_generated": False,
        "ai_summary_timestamp": None,
        "ai_model_used": "",
        "summary_quality_score": None,
        
        # 성과지표 (Phase 2)
        "first_response_time": None,
        "resolution_time": None,
        "customer_satisfaction": None,
        "escalation_count": 0,
        
        # 메타데이터 버전
        "metadata_version": "1.0",
        "last_normalized_at": None
    }
    
    # 허용되는 값 범위 정의
    ALLOWED_VALUES = {
        "priority": [1, 2, 3, 4, 5],
        "complexity_level": ["low", "medium", "high"],
        "status": [2, 3, 4, 5, 6],  # Freshdesk 표준: 2=Open, 3=Pending, 4=Resolved, 5=Closed, 6=Spam
        "metadata_version": ["1.0", "1.1", "1.2"]
    }
    
    # Status 코드 매핑 (참고용)
    STATUS_MAPPING = {
        2: "Open",
        3: "Pending", 
        4: "Resolved",
        5: "Closed",
        6: "Spam"
    }
    
    @classmethod
    def normalize(cls, raw_metadata: Any) -> Dict[str, Any]:
        """
        원시 메타데이터를 정규화된 형태로 변환
        
        Args:
            raw_metadata: 원시 메타데이터 (dict, str, None 등)
            
        Returns:
            정규화된 메타데이터 dict
        """
        logger.debug(f"메타데이터 정규화 시작: {type(raw_metadata)}")
        
        # 1. 기본 구조 생성
        normalized = cls.DEFAULT_SCHEMA.copy()
        
        # 2. 입력 데이터 파싱
        if raw_metadata is None:
            logger.debug("메타데이터가 None임 - 기본값 사용")
        elif isinstance(raw_metadata, str):
            try:
                parsed = json.loads(raw_metadata)
                if isinstance(parsed, dict):
                    cls._merge_data(normalized, parsed)
                else:
                    logger.warning(f"JSON 파싱 결과가 dict가 아님: {type(parsed)}")
            except json.JSONDecodeError as e:
                logger.warning(f"메타데이터 JSON 파싱 실패: {e}")
        elif isinstance(raw_metadata, dict):
            cls._merge_data(normalized, raw_metadata)
        else:
            logger.warning(f"지원되지 않는 메타데이터 타입: {type(raw_metadata)}")
        
        # 3. 값 검증 및 정규화
        cls._validate_and_fix_values(normalized)
        
        # 4. 파생 필드 계산
        cls._calculate_derived_fields(normalized)
        
        # 5. 정규화 타임스탬프 추가
        normalized["last_normalized_at"] = datetime.utcnow().isoformat()
        
        logger.debug(f"메타데이터 정규화 완료: {len(normalized)}개 필드")
        return normalized
    
    @classmethod
    def _merge_data(cls, target: Dict[str, Any], source: Dict[str, Any]) -> None:
        """소스 데이터를 타겟에 안전하게 병합"""
        for key, value in source.items():
            if key in cls.DEFAULT_SCHEMA:
                # 값 검증 후 병합
                validated_value = cls._validate_single_value(key, value)
                target[key] = validated_value
            else:
                # 알려지지 않은 필드는 로깅만
                logger.debug(f"알려지지지 않은 메타데이터 필드 무시: {key}")
    
    @classmethod
    def _validate_single_value(cls, field_name: str, value: Any) -> Any:
        """
        개별 필드 값을 검증하되 원본 API 응답을 최대한 보존
        
        Args:
            field_name: 필드명
            value: 검증할 값
            
        Returns:
            원본 값 (특별한 경우에만 변환)
        """
        # status 필드만 특별 처리 (문자열 -> 숫자 변환)
        if field_name == "status":
            return cls._convert_status_to_id(value)
        
        # 그 외 모든 필드는 원본 값 그대로 보존
        # Freshdesk API 응답의 null, 문자열, 숫자 등을 그대로 유지
        logger.debug(f"{field_name} 원본 값 보존: {value} (타입: {type(value)})")
        return value
    
    @classmethod
    def _validate_and_fix_values(cls, metadata: Dict[str, Any]) -> None:
        """원본 API 응답 데이터 보존 - 최소한의 일관성 검증만 수행"""
        
        # 파생 필드들만 계산하여 설정 (원본 데이터는 건드리지 않음)
        # 예: attachment_count와 attachments 배열 길이 일치
        attachments = metadata.get("attachments", [])
        if isinstance(attachments, list):
            # attachment_count는 실제 배열 크기로 설정 (원본이 None이어도 계산값 사용)
            metadata["attachment_count"] = len(attachments)
            logger.debug(f"attachment_count를 실제 배열 길이로 설정: {len(attachments)}")
        
        # conversation_count도 마찬가지로 파생 필드 처리
        conversations = metadata.get("conversations", [])
        if isinstance(conversations, list):
            metadata["conversation_count"] = len(conversations)
            logger.debug(f"conversation_count를 실제 배열 길이로 설정: {len(conversations)}")
        
        logger.debug("원본 데이터 보존 완료 - 타입 변환 없음")
    
    @classmethod
    def _calculate_derived_fields(cls, metadata: Dict[str, Any]) -> None:
        """파생 필드 계산"""
        
        # 첨부파일 관련 파생 필드
        attachments = metadata.get("attachments", [])
        if attachments:
            metadata["has_attachments"] = True
            metadata["attachment_count"] = len(attachments)
            
            # 첨부파일 유형 분석
            attachment_types = []
            has_images = False
            has_documents = False
            has_large_files = False
            
            for attachment in attachments:
                if isinstance(attachment, dict):
                    content_type = attachment.get("content_type", "")
                    size = attachment.get("size", 0)
                    
                    if content_type:
                        # 메인 타입 추출
                        main_type = content_type.split("/")[0] if "/" in content_type else content_type
                        if main_type not in attachment_types:
                            attachment_types.append(main_type)
                        
                        # 이미지/문서 여부 확인
                        if main_type == "image":
                            has_images = True
                        elif main_type in ["application", "text"]:
                            has_documents = True
                    
                    # 대용량 파일 여부 (5MB 이상)
                    if isinstance(size, (int, float)) and size > 5 * 1024 * 1024:
                        has_large_files = True
            
            metadata["attachment_types"] = attachment_types
            metadata["has_image_attachments"] = has_images
            metadata["has_document_attachments"] = has_documents
            metadata["large_attachments"] = has_large_files
        else:
            metadata["has_attachments"] = False
            metadata["attachment_count"] = 0
        
        # 대화 관련 파생 필드
        conv_count = metadata.get("conversation_count", 0)
        metadata["has_conversations"] = conv_count > 0
    
    @classmethod
    def extract_from_original_data(cls, original_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        원본 데이터에서 메타데이터 추출 - 원본 API 응답 그대로 보존
        
        Args:
            original_data: 원본 티켓 데이터 (Freshdesk API 응답)
            
        Returns:
            추출된 메타데이터 (원본 값과 타입 보존)
        """
        logger.debug("원본 데이터에서 메타데이터 추출 시작 - 원본 보존 모드")
        
        # 기본 스키마로 시작하되, 원본 데이터로 덮어쓰기
        extracted = cls.DEFAULT_SCHEMA.copy()
        
        # 원본 API 필드들을 그대로 보존 (타입 변환 없음)
        preserved_fields = [
            "subject", "status", "priority", "created_at", "updated_at",
            "id", "description", "description_text", "requester_id"
        ]
        
        for field in preserved_fields:
            if field in original_data:
                # 원본 값과 타입 그대로 보존
                extracted[field] = original_data[field]
                logger.debug(f"원본 필드 보존: {field} = {original_data[field]} (타입: {type(original_data[field])})")
        
        # original_id 처리: API의 id 필드를 벡터DB용 문자열 ID로 변환
        if "id" in original_data and original_data["id"] is not None:
            extracted["original_id"] = str(original_data["id"])
            logger.debug(f"original_id 생성: API id({original_data['id']}) -> original_id('{extracted['original_id']}')")
        
        # 중첩 객체에서 안전하게 추출 (None 체크 없이)
        if "company" in original_data and original_data["company"]:
            extracted["company_name"] = original_data["company"].get("name")
        
        if "requester" in original_data and original_data["requester"]:
            extracted["customer_email"] = original_data["requester"].get("email")
        
        if "responder" in original_data and original_data["responder"]:
            extracted["agent_name"] = original_data["responder"].get("name")
        
        if "group" in original_data and original_data["group"]:
            extracted["department"] = original_data["group"].get("name")
        
        if "product" in original_data and original_data["product"]:
            extracted["product_version"] = original_data["product"].get("name")
        
        # 배열 필드들 원본 보존
        if "conversations" in original_data:
            extracted["conversations"] = original_data["conversations"]
        
        if "all_attachments" in original_data:
            extracted["attachments"] = original_data["all_attachments"]
        
        # 복잡도는 계산하되 원본 데이터 기반
        complexity = cls._estimate_complexity(original_data)
        extracted["complexity_level"] = complexity
        
        logger.debug(f"원본 데이터 추출 완료: {len([k for k, v in extracted.items() if k in original_data])}개 원본 필드 보존")
        
        # 정규화 처리 (이제 원본 보존)
        return cls.normalize(extracted)
    
    @classmethod
    def _safe_int(cls, value: Any, default: int = 0) -> int:
        """안전한 정수 변환"""
        try:
            return int(value) if value is not None else default
        except (ValueError, TypeError):
            return default
    
    @classmethod
    def _estimate_complexity(cls, original_data: Dict[str, Any]) -> str:
        """티켓 복잡도 추정"""
        score = 0
        
        # 대화 수에 따른 점수
        conv_count = len(original_data.get("conversations", []))
        if conv_count > 10:
            score += 3
        elif conv_count > 5:
            score += 2
        elif conv_count > 2:
            score += 1
        
        # 첨부파일 수에 따른 점수
        attachment_count = len(original_data.get("all_attachments", []))
        if attachment_count > 5:
            score += 2
        elif attachment_count > 2:
            score += 1
        
        # 우선순위에 따른 점수
        priority = cls._safe_int(original_data.get("priority"), 1)
        if priority >= 4:
            score += 2
        elif priority >= 3:
            score += 1
        
        # 설명 길이에 따른 점수
        description_length = len(original_data.get("description", ""))
        if description_length > 1000:
            score += 2
        elif description_length > 500:
            score += 1
        
        # 점수에 따른 복잡도 결정
        if score >= 6:
            return "high"
        elif score >= 3:
            return "medium"
        else:
            return "low"
    
    @classmethod
    def update_ai_processing_info(cls, metadata: Dict[str, Any], 
                                 model_used: str, quality_score: Optional[float] = None) -> Dict[str, Any]:
        """AI 처리 정보 업데이트"""
        metadata = metadata.copy()
        metadata["ai_summary_generated"] = True
        metadata["ai_summary_timestamp"] = datetime.utcnow().isoformat()
        metadata["ai_model_used"] = model_used
        
        if quality_score is not None:
            metadata["summary_quality_score"] = quality_score
        
        return metadata
    
    @classmethod
    def _convert_status_to_id(cls, status_value: Any) -> int:
        """
        Status 값을 숫자 ID로 변환
        
        Args:
            status_value: 문자열 또는 숫자 status 값
            
        Returns:
            숫자 status ID
        """
        # None인 경우 기본값 반환 (원본 API 응답 보존 정책)
        if status_value is None:
            logger.debug("status가 None임 - 기본값(2=Open) 사용")
            return 2
        
        # 이미 숫자인 경우
        if isinstance(status_value, int):
            if status_value in cls.ALLOWED_VALUES["status"]:
                return status_value
            else:
                logger.warning(f"허용되지 않은 status ID: {status_value}, 기본값(2) 사용")
                return 2
        
        # 문자열인 경우 변환
        if isinstance(status_value, str):
            status_lower = status_value.lower().strip()
            text_to_id_mapping = {
                "open": 2,
                "pending": 3,
                "resolved": 4,
                "closed": 5,
                "spam": 6,
                "": 2  # 빈 문자열은 Open으로
            }
            
            if status_lower in text_to_id_mapping:
                return text_to_id_mapping[status_lower]
            else:
                logger.warning(f"알 수 없는 status 텍스트: {status_value}, 기본값(2) 사용")
                return 2
        
        # 기타 타입인 경우
        logger.warning(f"지원되지 않는 status 타입: {type(status_value)}, 기본값(2) 사용")
        return 2
    
    @classmethod
    def get_status_text(cls, status_id: int) -> str:
        """
        Status ID를 텍스트로 변환
        
        Args:
            status_id: 숫자 status ID
            
        Returns:
            Status 텍스트
        """
        return cls.STATUS_MAPPING.get(status_id, f"Unknown({status_id})")
