"""
환경 설정 관리 모듈

이 모듈은 Pydantic을 사용하여 환경변수와 애플리케이션 설정을 관리합니다.
모든 설정은 .env 파일 또는 환경변수에서 로드됩니다.

개발자는 Settings 클래스의 인스턴스를 통해 모든 설정에 타입이 지정된 상태로 접근할 수 있습니다.
"""

import json
import os
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseSettings, Field, validator


class Settings(BaseSettings):
    """
    애플리케이션 설정을 관리하는 클래스입니다.
    
    모든 설정은 환경변수 또는 .env 파일에서 로드되며, 
    타입 힌트와 기본값을 통해 안전한 설정 관리를 제공합니다.
    """
    # Freshdesk API 설정
    FRESHDESK_API_KEY: str = Field(..., description="Freshdesk API 키")
    FRESHDESK_DOMAIN: str = Field(..., description="Freshdesk 도메인 (예: company.freshdesk.com)")
    
    # Qdrant Cloud 설정
    QDRANT_URL: str = Field(..., description="Qdrant Cloud URL")
    QDRANT_API_KEY: str = Field(..., description="Qdrant Cloud API 키")
    
    # LLM API 키 설정
    ANTHROPIC_API_KEY: Optional[str] = Field(None, description="Anthropic API 키")
    OPENAI_API_KEY: Optional[str] = Field(None, description="OpenAI API 키")
    GOOGLE_API_KEY: Optional[str] = Field(None, description="Google Gemini API 키")
    PERPLEXITY_API_KEY: Optional[str] = Field(None, description="Perplexity API 키")
    
    # 애플리케이션 설정
    COMPANY_ID: str = Field(..., description="기본 회사 ID")
    PROCESS_ATTACHMENTS: bool = Field(True, description="첨부 파일 처리 여부")
    EMBEDDING_MODEL: str = Field("text-embedding-3-small", description="임베딩 모델 이름")
    LOG_LEVEL: str = Field("INFO", description="로깅 레벨")
    MAX_TOKENS: int = Field(4096, description="LLM 최대 토큰 수")
    
    # 캐싱 설정
    CACHE_TTL: int = Field(600, description="캐시 TTL (초)")
    CACHE_SIZE: int = Field(100, description="캐시 최대 항목 수")
    
    # CORS 설정
    CORS_ORIGINS: List[str] = Field(
        ["*"], description="CORS 허용 오리진 리스트"
    )
    
    # 애플리케이션 경로 설정
    APP_ROOT_PATH: str = Field("", description="API 루트 경로")
    
    @validator("FRESHDESK_DOMAIN")
    def validate_freshdesk_domain(cls, v):
        """Freshdesk 도메인에 'https://' 또는 'http://'가 포함되어 있으면 제거합니다."""
        if v.startswith(("http://", "https://")):
            # URL에서 도메인 부분만 추출
            from urllib.parse import urlparse
            parsed_url = urlparse(v)
            return parsed_url.netloc
        return v

    @property
    def extracted_company_id(self) -> str:
        """
        FRESHDESK_DOMAIN에서 company_id를 자동으로 추출합니다.
        
        Returns:
            str: 추출된 company_id
        """
        domain = self.FRESHDESK_DOMAIN
        
        # .freshdesk.com이 포함된 경우 제거
        if ".freshdesk.com" in domain:
            company_id = domain.replace(".freshdesk.com", "")
        else:
            company_id = domain
        
        # https:// 또는 http://가 포함된 경우 제거 (validator에서 이미 처리되지만 안전장치)
        if company_id.startswith(("https://", "http://")):
            from urllib.parse import urlparse
            parsed_url = urlparse(company_id)
            company_id = parsed_url.netloc.replace(".freshdesk.com", "")
        
        return company_id

    @property
    def freshdesk_api_headers(self) -> Dict[str, str]:
        """
        Freshdesk API 호출에 사용할 헤더를 반환합니다.
        X-Company-ID가 자동으로 포함됩니다.
        
        Returns:
            Dict[str, str]: API 호출용 헤더
        """
        return {
            "Content-Type": "application/json",
            "X-Company-ID": self.extracted_company_id
        }

    class Config:
        """Pydantic 설정 클래스"""
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """
    설정을 로드하고 캐싱된 인스턴스를 반환합니다.
    
    환경변수 'ENV_PATH'가 설정되어 있으면 해당 경로의 .env 파일을 사용합니다.
    
    Returns:
        Settings: 환경 설정 인스턴스
    """
    env_path = os.environ.get("ENV_PATH")
    
    if env_path:
        return Settings(_env_file=env_path)
    
    # 기본 경로에서 .env 파일 찾기
    base_dir = Path(__file__).parent.parent
    default_env_path = base_dir / ".env"
    
    if default_env_path.exists():
        return Settings(_env_file=str(default_env_path))
    
    return Settings()


def export_settings_for_taskmaster():
    """
    Task Master에 사용할 환경 변수를 내보냅니다.
    
    이 함수는 명령줄에서 직접 실행될 때 유용합니다:
    python -m core.config
    
    현재 .env 파일에서 로드된 설정을 환경 변수로 내보냅니다.
    """
    try:
        # 설정 로드
        config = get_settings()
        # 설정을 딕셔너리로 변환
        settings_dict = config.dict()
        
        # 환경 변수로 내보내고 결과 출력
        print("Task Master에 사용할 환경 변수를 내보냅니다...\n")
        print("# 다음 명령어를 실행하여 환경 변수를 설정할 수 있습니다:")
        
        # Bash 스크립트용 명령어 생성
        for key, value in settings_dict.items():
            if value is not None:
                if isinstance(value, list):
                    value = json.dumps(value)
                print(f'export {key}="{value}"')
        
        print("\n✅ 환경 변수가 준비되었습니다.")
    except Exception as e:
        print(f"⚠️  설정을 내보내는 중 오류가 발생했습니다: {str(e)}")
        sys.exit(1)


# 전역 설정 인스턴스 생성
settings = get_settings()

# 스크립트로 직접 실행될 때 환경 변수 내보내기
if __name__ == "__main__":
    export_settings_for_taskmaster()
