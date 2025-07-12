"""
애플리케이션 상수 정의
"""

import os
from typing import Dict, Any, Set
from enum import Enum


# =================================================================
# 기존 문서 타입 정의 (하위 호환성 유지)
# =================================================================
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
    
    # 기본 tenant_id
    DEFAULT_TENANT_ID = os.getenv("TENANT_ID", "example-company")
    
    # 벡터 DB 컬렉션명 패턴
    VECTOR_COLLECTION_PATTERN = "{tenant_id}_documents"
    
    # 지원하는 문서 타입들
    SUPPORTED_DOC_TYPES = {
        DocType.TICKET.value,
        DocType.KNOWLEDGE_BASE.value,
        DocType.ATTACHMENT.value,
        DocType.IMAGE.value,
    }


# =================================================================
# 새로운 최적화된 상수들
# =================================================================

# 캐시 설정
class CacheConfig:
    """캐시 관련 상수"""
    DEFAULT_TTL = int(os.getenv("CACHE_TTL_DEFAULT", "3600"))
    TICKET_CONTEXT_TTL = int(os.getenv("CACHE_TTL_TICKET_CONTEXT", "3600"))
    TICKET_SUMMARY_TTL = int(os.getenv("CACHE_TTL_TICKET_SUMMARY", "1800"))
    LLM_RESPONSE_TTL = int(os.getenv("CACHE_TTL_LLM_RESPONSE", "7200"))
    VECTOR_SEARCH_TTL = int(os.getenv("CACHE_TTL_VECTOR_SEARCH", "1800"))
    
    # 캐시 크기 제한
    MAX_TICKET_CONTEXT_ITEMS = 1000
    MAX_TICKET_SUMMARY_ITEMS = 500
    MAX_LLM_RESPONSE_ITEMS = 2000
    MAX_VECTOR_SEARCH_ITEMS = 1500


# 검색 설정
class SearchConfig:
    """검색 관련 설정값"""
    SIMILAR_TICKETS_COUNT = int(os.getenv("SIMILAR_TICKETS_MAX_COUNT", "3"))
    KB_DOCUMENTS_COUNT = int(os.getenv("KB_DOCUMENTS_MAX_COUNT", "3"))
    VECTOR_SEARCH_SCORE_THRESHOLD = float(os.getenv("VECTOR_SEARCH_SCORE_THRESHOLD", "0.7"))


# API 제한값
class APILimits:
    """API 관련 제한값"""
    MAX_TICKETS_PER_REQUEST = 100
    MAX_CONVERSATIONS_PER_TICKET = 20
    MAX_CHARS_PER_CONVERSATION = 1000
    MAX_ATTACHMENTS_PER_TICKET = 50
    MAX_KB_DOCUMENTS = 10
    MAX_SIMILAR_TICKETS = int(os.getenv("SIMILAR_TICKETS_MAX_COUNT", "3"))
    
    # 배치 처리
    DEFAULT_BATCH_SIZE = int(os.getenv("DEFAULT_BATCH_SIZE", "50"))
    MAX_BATCH_SIZE = int(os.getenv("MAX_BATCH_SIZE", "100"))
    LLM_BATCH_SIZE = int(os.getenv("LLM_BATCH_SIZE", "20"))
    
    # 타임아웃
    DEFAULT_TIMEOUT = 30
    LLM_TIMEOUT = float(os.getenv("LLM_GLOBAL_TIMEOUT", "8.0"))
    VECTOR_SEARCH_TIMEOUT = 10
    
    # 동시 요청
    MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", "10"))
    MAX_CONCURRENT_LLM_CALLS = 5


# 모델 설정
class ModelConfig:
    """LLM 모델 설정"""
    # 메인 티켓 요약
    MAIN_TICKET_MODEL = os.getenv("MAIN_TICKET_MODEL", "openai/gpt-4o-mini")
    MAIN_TICKET_MAX_TOKENS = int(os.getenv("MAIN_TICKET_MAX_TOKENS", "800"))
    MAIN_TICKET_TEMPERATURE = float(os.getenv("MAIN_TICKET_TEMPERATURE", "0.1"))
    
    # 유사 티켓 요약
    SIMILAR_TICKET_MODEL = os.getenv("SIMILAR_TICKET_MODEL", "anthropic/claude-3-haiku-20240307")
    SIMILAR_TICKET_MAX_TOKENS = int(os.getenv("SIMILAR_TICKET_MAX_TOKENS", "600"))
    SIMILAR_TICKET_TEMPERATURE = float(os.getenv("SIMILAR_TICKET_TEMPERATURE", "0.2"))
    
    # 쿼리 응답
    QUERY_RESPONSE_MODEL = os.getenv("QUERY_RESPONSE_MODEL", "anthropic/claude-3-5-sonnet-20241022")
    QUERY_RESPONSE_MAX_TOKENS = int(os.getenv("QUERY_RESPONSE_MAX_TOKENS", "2000"))
    QUERY_RESPONSE_TEMPERATURE = float(os.getenv("QUERY_RESPONSE_TEMPERATURE", "0.3"))
    
    # 대화 필터링
    CONVERSATION_FILTER_MODEL = os.getenv("CONVERSATION_FILTER_MODEL", "gemini/gemini-1.5-flash")
    CONVERSATION_FILTER_MAX_TOKENS = int(os.getenv("CONVERSATION_FILTER_MAX_TOKENS", "1000"))
    CONVERSATION_FILTER_TEMPERATURE = float(os.getenv("CONVERSATION_FILTER_TEMPERATURE", "0.1"))
    
    # 폴백 설정
    ENABLE_MODEL_FALLBACK = os.getenv("ENABLE_MODEL_FALLBACK", "true").lower() == "true"
    MODEL_FALLBACK_CHAIN = os.getenv("MODEL_FALLBACK_CHAIN", "anthropic,openai,gemini").split(",")
    
    @classmethod
    def get_model_config(cls, use_case: str) -> Dict[str, Any]:
        """용도별 모델 설정 반환"""
        configs = {
            "main_ticket": {
                "model": cls.MAIN_TICKET_MODEL,
                "max_tokens": cls.MAIN_TICKET_MAX_TOKENS,
                "temperature": cls.MAIN_TICKET_TEMPERATURE
            },
            "similar_ticket": {
                "model": cls.SIMILAR_TICKET_MODEL,
                "max_tokens": cls.SIMILAR_TICKET_MAX_TOKENS,
                "temperature": cls.SIMILAR_TICKET_TEMPERATURE
            },
            "query_response": {
                "model": cls.QUERY_RESPONSE_MODEL,
                "max_tokens": cls.QUERY_RESPONSE_MAX_TOKENS,
                "temperature": cls.QUERY_RESPONSE_TEMPERATURE
            },
            "conversation_filter": {
                "model": cls.CONVERSATION_FILTER_MODEL,
                "max_tokens": cls.CONVERSATION_FILTER_MAX_TOKENS,
                "temperature": cls.CONVERSATION_FILTER_TEMPERATURE
            }
        }
        return configs.get(use_case, configs["query_response"])


# Rate Limiting
class RateLimitConfig:
    """Rate Limiting 설정"""
    GLOBAL_PER_MINUTE = int(os.getenv("RATE_LIMIT_GLOBAL_PER_MINUTE", "1000"))
    API_PER_MINUTE = int(os.getenv("RATE_LIMIT_API_PER_MINUTE", "100"))
    HEAVY_PER_MINUTE = int(os.getenv("RATE_LIMIT_HEAVY_PER_MINUTE", "20"))
    
    # 버스트 허용량
    GLOBAL_BURST = 50
    API_BURST = 10
    HEAVY_BURST = 5
    
    # 인증 실패 제한
    MAX_AUTH_FAILURES = 5
    AUTH_LOCKOUT_DURATION = 300  # 5분


# 벡터 검색 설정
class VectorSearchConfig:
    """벡터 검색 관련 설정"""
    DEFAULT_TOP_K = 5
    MAX_TOP_K = 20
    MIN_SCORE_THRESHOLD = 0.7
    
    # 검색 가중치
    TITLE_WEIGHT = 0.3
    CONTENT_WEIGHT = 0.5
    METADATA_WEIGHT = 0.2
    
    # 검색 필터
    DEFAULT_DAYS_BACK = 90
    MAX_DAYS_BACK = 365


# 대화 필터링 설정
class ConversationFilterConfig:
    """대화 필터링 설정"""
    ENABLED = os.getenv("ENABLE_CONVERSATION_FILTERING", "true").lower() == "true"
    TOKEN_BUDGET = int(os.getenv("CONVERSATION_TOKEN_BUDGET", "12000"))
    IMPORTANCE_THRESHOLD = float(os.getenv("CONVERSATION_IMPORTANCE_THRESHOLD", "0.4"))
    FILTERING_MODE = os.getenv("CONVERSATION_FILTERING_MODE", "conservative")
    
    # 언어별 최소 길이
    MIN_LENGTH_KO = 10
    MIN_LENGTH_EN = 20
    MIN_LENGTH_DEFAULT = 15
    
    # 전략별 최대 대화 수
    STRATEGY_LIMITS = {
        "tiny": 15,
        "small": 35,
        "medium": 70,
        "large": 150
    }


# 파일 처리 설정
class FileProcessingConfig:
    """파일 처리 관련 설정"""
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS = {
        'pdf', 'doc', 'docx', 'txt', 'md', 'rtf',
        'xls', 'xlsx', 'csv',
        'png', 'jpg', 'jpeg', 'gif', 'bmp',
        'zip', 'tar', 'gz'
    }
    
    # OCR 설정
    ENABLE_OCR = True
    OCR_LANGUAGES = ['eng', 'kor']
    
    # 이미지 처리
    MAX_IMAGE_DIMENSION = 4096
    THUMBNAIL_SIZE = (256, 256)


# 로깅 설정
class LoggingConfig:
    """로깅 관련 설정"""
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT = "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
    
    # 로그 파일 설정
    ENABLE_FILE_LOGGING = False
    LOG_FILE_PATH = "logs/app.log"
    LOG_FILE_MAX_SIZE = 100 * 1024 * 1024  # 100MB
    LOG_FILE_BACKUP_COUNT = 5
    
    # 성능 로깅
    LOG_SLOW_REQUESTS = True
    SLOW_REQUEST_THRESHOLD = 5.0  # 5초


# 보안 설정
class SecurityConfig:
    """보안 관련 설정"""
    # JWT 설정
    JWT_SECRET = os.getenv("JWT_SECRET", "change-this-in-production")
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRATION_HOURS = int(os.getenv("SESSION_TIMEOUT_HOURS", "24"))
    
    # API 키 검증
    VALIDATE_API_KEYS = True
    API_KEY_MIN_LENGTH = 32
    
    # 헤더 검증
    REQUIRED_HEADERS = ["X-Tenant-ID", "X-Platform", "X-Domain", "X-API-Key"]
    
    # IP 화이트리스트 (비어있으면 모든 IP 허용)
    IP_WHITELIST = []
    
    # CORS 설정
    ALLOWED_ORIGINS = ["*"]  # 운영 환경에서는 제한 필요


# 기타 설정
class MiscConfig:
    """기타 설정"""
    # 환경
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
    IS_PRODUCTION = ENVIRONMENT == "production"
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    
    # 서버
    HOST = os.getenv("HOST", "localhost")
    PORT = int(os.getenv("PORT", "8000"))
    
    # 데이터베이스
    DATABASE_TYPE = os.getenv("DATABASE_TYPE", "sqlite")
    
    # 기능 플래그
    PROCESS_ATTACHMENTS = os.getenv("PROCESS_ATTACHMENTS", "true").lower() == "true"
    ENABLE_METRICS = True
    ENABLE_HEALTH_CHECK = True