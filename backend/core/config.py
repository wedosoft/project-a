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
import sqlite3
from urllib.parse import urlparse
import boto3
from botocore.exceptions import ClientError

# 환경변수 로드 - 명시적으로 .env 파일 경로를 지정
from dotenv import load_dotenv
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 환경변수 로드
backend_dir = Path(__file__).parent.parent  # core 디렉토리의 상위(backend) 디렉토리
dotenv_path = os.path.join(backend_dir, ".env")
load_dotenv(dotenv_path=dotenv_path)

# 환경변수 로드 후 디버그 메시지
if os.getenv("DEBUG") == "true":
    print(f".env 파일 로드: {dotenv_path}")
    print(f"QDRANT_URL: {'설정됨' if os.getenv('QDRANT_URL') else '미설정'}")
    print(f"OPENAI_API_KEY: {'설정됨' if os.getenv('OPENAI_API_KEY') else '미설정'}")


class Settings(BaseSettings):
    """
    애플리케이션 설정을 관리하는 클래스입니다.
    
    멀티테넌트 환경 설계:
    - 환경변수: 전역 설정(DB 연결, API 키 등)만 관리
    - 헤더: 요청별 테넌트 정보(X-Tenant-ID, X-Platform, X-Domain, X-API-Key)
    - TENANT_ID 환경변수는 개발/테스트용 기본값, 운영에서는 헤더 우선 사용
    
    모든 설정은 환경변수 또는 .env 파일에서 로드되며, 
    타입 힌트와 기본값을 통해 안전한 설정 관리를 제공합니다.
    """
    # Pydantic V2 스타일의 설정
    model_config = SettingsConfigDict(
        env_file=dotenv_path,
        env_file_encoding="utf-8",
        extra="ignore"  # 추가 환경변수 무시
    )
    # AWS 설정
    AWS_REGION: str = Field(default="us-west-2", description="AWS 리전")
    AWS_ACCESS_KEY_ID: Optional[str] = Field(None, description="AWS Access Key ID")
    AWS_SECRET_ACCESS_KEY: Optional[str] = Field(None, description="AWS Secret Access Key")
    
    # 멀티테넌트 DB 설정
    # 개발환경: SQLite, 운영환경: PostgreSQL
    DATABASE_URL: Optional[str] = Field(None, description="운영환경 PostgreSQL URL")
    DB_SCHEMA_PREFIX: str = Field("tenant_", description="테넌트 스키마 접두사")
    
    # 멀티테넌트 환경 설정 방식
    # 운영환경: 헤더(X-Tenant-ID, X-Platform, X-Domain, X-API-Key)로 요청별 테넌트 정보 전달
    # 개발환경: 아래 환경변수를 기본값으로 사용 (단일 테넌트 테스트용)
    API_KEY: Optional[str] = Field(None, alias="FRESHDESK_API_KEY", description="개발용 기본 API 키 (운영환경에서는 헤더 사용)")
    DOMAIN: Optional[str] = Field(None, alias="FRESHDESK_DOMAIN", description="개발용 기본 도메인 (운영환경에서는 헤더 사용)")
    PLATFORM: Optional[str] = Field("freshdesk", description="개발용 기본 플랫폼")
    
    # Qdrant Cloud 설정
    QDRANT_URL: str = Field(..., description="Qdrant Cloud URL")
    QDRANT_API_KEY: str = Field(..., description="Qdrant Cloud API 키")
    
    # LLM API 키 설정 (개발환경 fallback, 운영환경에서는 Secrets Manager 사용)
    ANTHROPIC_API_KEY: Optional[str] = Field(None, description="Anthropic API 키 (개발용, 운영환경에서는 Secrets Manager)")
    OPENAI_API_KEY: Optional[str] = Field(None, description="OpenAI API 키 (개발용, 운영환경에서는 Secrets Manager)")
    GOOGLE_API_KEY: Optional[str] = Field(None, description="Google Gemini API 키 (개발용, 운영환경에서는 Secrets Manager)")
    PERPLEXITY_API_KEY: Optional[str] = Field(None, description="Perplexity API 키 (개발용, 운영환경에서는 Secrets Manager)")
    DEEPSEEK_API_KEY: Optional[str] = Field(None, description="DeepSeek API 키 (개발용, 운영환경에서는 Secrets Manager)")
    OPENROUTER_API_KEY: Optional[str] = Field(None, description="OpenRouter API 키 (개발용, 운영환경에서는 Secrets Manager)")
    
    # 애플리케이션 설정 (멀티테넌트 환경 고려)
    TENANT_ID: Optional[str] = Field(None, description="기본 테넌트 ID (개발/테스트용, 운영환경에서는 헤더 사용)")
    PROCESS_ATTACHMENTS: bool = Field(True, description="첨부 파일 처리 여부")
    EMBEDDING_MODEL: str = Field("text-embedding-3-small", description="임베딩 모델 이름")
    LOG_LEVEL: str = Field("INFO", description="로깅 레벨")
    MAX_TOKENS: int = Field(4096, description="LLM 최대 토큰 수")
    
    # 개발 환경 설정
    DEBUG: bool = Field(False, description="디버그 모드 활성화 여부")
    HOST: str = Field("0.0.0.0", description="서버 호스트")
    PORT: int = Field(8000, description="서버 포트")
    
    # 캐싱 설정
    CACHE_TTL: int = Field(600, description="캐시 TTL (초)")
    CACHE_SIZE: int = Field(100, description="캐시 최대 항목 수")
    
    # Pydantic V2에서는 위의 model_config를 사용합니다
    
    # CORS 설정
    CORS_ORIGINS: List[str] = Field(
        ["*"], description="CORS 허용 오리진 리스트"
    )
    
    # 애플리케이션 경로 설정
    APP_ROOT_PATH: str = Field("", description="API 루트 경로")
    
    @field_validator("DOMAIN")
    def validate_domain(cls, v):
        """도메인에 'https://' 또는 'http://'가 포함되어 있으면 제거합니다."""
        if v is None:
            return v
        if v.startswith(("http://", "https://")):
            # URL에서 도메인 부분만 추출
            parsed_url = urlparse(v)
            return parsed_url.netloc
        return v

    @property
    def extracted_tenant_id(self) -> str:
        """
        DOMAIN에서 tenant_id를 자동으로 추출합니다.
        
        Returns:
            str: 추출된 tenant_id
        """
        domain = self.DOMAIN
        
        # 플랫폼별 도메인 확장자 제거
        if ".freshdesk.com" in domain:
            tenant_id = domain.replace(".freshdesk.com", "")
        elif ".zendesk.com" in domain:
            tenant_id = domain.replace(".zendesk.com", "")
        else:
            tenant_id = domain
        
        # https:// 또는 http://가 포함된 경우 제거 (validator에서 이미 처리되지만 안전장치)
        if tenant_id.startswith(("https://", "http://")):
            parsed_url = urlparse(tenant_id)
            # 플랫폼별 도메인 제거
            netloc = parsed_url.netloc
            if ".freshdesk.com" in netloc:
                tenant_id = netloc.replace(".freshdesk.com", "")
            elif ".zendesk.com" in netloc:
                tenant_id = netloc.replace(".zendesk.com", "")
            else:
                tenant_id = netloc
        
        return tenant_id

    @property
    def api_headers(self) -> Dict[str, str]:
        """
        API 호출에 사용할 헤더를 반환합니다.
        X-Tenant-ID가 자동으로 포함됩니다.
        
        Returns:
            Dict[str, str]: API 호출용 헤더
        """
        return {
            "Content-Type": "application/json",
            "X-Tenant-ID": self.extracted_tenant_id
        }

    # Pydantic V2에서는 model_config를 사용하며, Config 클래스는 더 이상 사용하지 않습니다.


class TenantConfig:
    """
    개별 테넌트(회사)의 설정을 관리하는 클래스
    """
    def __init__(self, tenant_id: str, platform: str, domain: str, api_key: str):
        self.tenant_id = tenant_id
        self.platform = platform
        self.domain = domain
        self.api_key = api_key
    
    def to_dict(self) -> Dict[str, str]:
        return {
            "tenant_id": self.tenant_id,
            "platform": self.platform,
            "domain": self.domain,
            "api_key": self.api_key
        }


class MultiTenantConfigManager:
    """
    멀티테넌트 환경에서 테넌트별 설정을 관리하는 클래스
    
    운영 방식:
    1. 개발환경: 환경변수에서 기본값 로드
    2. 운영환경: AWS Secrets Manager에서 테넌트별 설정 로드  
    3. DB: PostgreSQL 단일 인스턴스 + 테넌트별 스키마
    4. 벡터DB: Qdrant 단일 인스턴스 + tenant_id 필터링
    """
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.tenant_cache: Dict[str, TenantConfig] = {}
        self.secrets_client = None
        self._init_aws_client()
        self._init_storage()
    
    def _init_aws_client(self):
        """AWS Secrets Manager 클라이언트 초기화"""
        try:
            self.secrets_client = boto3.client(
                'secretsmanager',
                region_name=self.settings.AWS_REGION,
                aws_access_key_id=self.settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=self.settings.AWS_SECRET_ACCESS_KEY
            )
        except Exception as e:
            print(f"AWS Secrets Manager 클라이언트 초기화 실패: {e}")
            self.secrets_client = None
    
    def _init_storage(self):
        """
        테넌트 설정 저장소 초기화
        개발환경: SQLite, 운영환경: PostgreSQL + 테넌트별 스키마
        """
        if self.settings.DATABASE_URL:
            # 운영환경: PostgreSQL
            self._init_postgresql()
        else:
            # 개발환경: SQLite  
            self._init_sqlite()
    
    def _init_sqlite(self):
        """개발환경: SQLite 초기화"""
        db_path = Path(__file__).parent.parent / "tenant_configs.db"
        
        with sqlite3.connect(str(db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tenant_configs (
                    tenant_id TEXT PRIMARY KEY,
                    platform TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    api_key TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
    
    def _init_postgresql(self):
        """운영환경: PostgreSQL + 테넌트별 스키마 초기화"""
        # TODO: PostgreSQL 연결 및 스키마 초기화
        # psycopg2 또는 asyncpg 사용
        pass
    
    def get_tenant_config(self, tenant_id: str) -> Optional[TenantConfig]:
        """
        테넌트 설정 조회 우선순위:
        1. 캐시 
        2. AWS Secrets Manager (운영환경)
        3. DB (운영환경)
        4. 환경변수 (개발환경)
        
        Args:
            tenant_id: 테넌트 ID
            
        Returns:
            TenantConfig: 테넌트 설정 또는 None
        """
        # 1. 캐시에서 조회
        if tenant_id in self.tenant_cache:
            return self.tenant_cache[tenant_id]
        
        # 2. AWS Secrets Manager에서 조회 (운영환경)
        secrets_config = self._load_from_secrets_manager(tenant_id)
        if secrets_config:
            self.tenant_cache[tenant_id] = secrets_config
            return secrets_config
        
        # 3. DB에서 조회 (백업용)
        db_config = self._load_from_db(tenant_id)
        if db_config:
            self.tenant_cache[tenant_id] = db_config
            return db_config
        
        # 4. 개발환경: 환경변수 기본값 사용
        if self.settings.API_KEY and self.settings.DOMAIN:
            default_config = TenantConfig(
                tenant_id=tenant_id,
                platform=self.settings.PLATFORM,
                domain=self.settings.DOMAIN,
                api_key=self.settings.API_KEY
            )
            self.tenant_cache[tenant_id] = default_config
            return default_config
        
        return None
    
    def _load_from_secrets_manager(self, tenant_id: str) -> Optional[TenantConfig]:
        """AWS Secrets Manager에서 테넌트 설정 로드"""
        if not self.secrets_client:
            return None
        
        secret_name = f"tenant-configs/{tenant_id}"
        
        try:
            response = self.secrets_client.get_secret_value(SecretId=secret_name)
            secret_data = json.loads(response['SecretString'])
            
            return TenantConfig(
                tenant_id=tenant_id,
                platform=secret_data['platform'],
                domain=secret_data['domain'], 
                api_key=secret_data['api_key']
            )
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                print(f"시크릿을 찾을 수 없음: {secret_name}")
            else:
                print(f"AWS Secrets Manager 오류 ({tenant_id}): {e}")
        except Exception as e:
            print(f"시크릿 파싱 오류 ({tenant_id}): {e}")
        
        return None
    
    def save_tenant_config_to_secrets(self, config: TenantConfig) -> bool:
        """
        테넌트 설정을 AWS Secrets Manager에 저장
        
        Args:
            config: 저장할 테넌트 설정
            
        Returns:
            bool: 성공 여부
        """
        if not self.secrets_client:
            return False
        
        secret_name = f"tenant-configs/{config.tenant_id}"
        secret_value = {
            "platform": config.platform,
            "domain": config.domain,
            "api_key": config.api_key
        }
        
        try:
            # 시크릿이 존재하면 업데이트, 없으면 생성
            try:
                self.secrets_client.update_secret(
                    SecretId=secret_name,
                    SecretString=json.dumps(secret_value)
                )
            except ClientError as e:
                if e.response['Error']['Code'] == 'ResourceNotFoundException':
                    # 시크릿이 없으면 생성
                    self.secrets_client.create_secret(
                        Name=secret_name,
                        SecretString=json.dumps(secret_value),
                        Description=f"테넌트 설정: {config.tenant_id}"
                    )
                else:
                    raise
            
            # 캐시 업데이트
            self.tenant_cache[config.tenant_id] = config
            return True
            
        except Exception as e:
            print(f"AWS Secrets Manager 저장 실패 ({config.tenant_id}): {e}")
            return False
    
    def _load_from_db(self, tenant_id: str) -> Optional[TenantConfig]:
        """DB에서 테넌트 설정 로드"""
        db_path = Path(__file__).parent.parent / "tenant_configs.db"
        
        try:
            with sqlite3.connect(str(db_path)) as conn:
                cursor = conn.execute(
                    "SELECT platform, domain, api_key FROM tenant_configs WHERE tenant_id = ?",
                    (tenant_id,)
                )
                row = cursor.fetchone()
                
                if row:
                    platform, domain, api_key = row
                    return TenantConfig(tenant_id, platform, domain, api_key)
        except Exception as e:
            print(f"DB에서 테넌트 설정 로드 실패 ({tenant_id}): {e}")
        
        return None
    
    def save_tenant_config(self, config: TenantConfig) -> bool:
        """
        테넌트 설정 저장
        
        Args:
            config: 저장할 테넌트 설정
            
        Returns:
            bool: 성공 여부
        """
        db_path = Path(__file__).parent.parent / "tenant_configs.db"
        
        try:
            with sqlite3.connect(str(db_path)) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO tenant_configs 
                    (tenant_id, platform, domain, api_key, updated_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (config.tenant_id, config.platform, config.domain, config.api_key))
                conn.commit()
                
                # 캐시 업데이트
                self.tenant_cache[config.tenant_id] = config
                return True
        except Exception as e:
            print(f"테넌트 설정 저장 실패 ({config.tenant_id}): {e}")
            return False
    
    def get_config_from_headers(
        self, 
        tenant_id: str, 
        platform: str, 
        domain: str, 
        api_key: str
    ) -> TenantConfig:
        """
        헤더에서 받은 정보로 TenantConfig 생성
        헤더 정보가 우선순위를 가짐 (멀티테넌트의 핵심)
        
        Args:
            tenant_id: X-Tenant-ID 헤더값
            platform: X-Platform 헤더값  
            domain: X-Domain 헤더값
            api_key: X-API-Key 헤더값
            
        Returns:
            TenantConfig: 헤더 기반 테넌트 설정
        """
        return TenantConfig(tenant_id, platform, domain, api_key)


class MultiTenantDatabaseManager:
    """
    멀티테넌트 데이터베이스 스키마 관리
    
    전략: 테넌트별 스키마 (권장)
    - 단일 PostgreSQL 인스턴스
    - 테넌트별 스키마: tenant_company_a, tenant_company_b 
    - 각 스키마에 동일한 테이블 구조
    - 개발환경: SQLite 파일별 격리 (현재 방식 유지)
    """
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.schema_prefix = settings.DB_SCHEMA_PREFIX
    
    def get_tenant_schema_name(self, tenant_id: str, platform: str) -> str:
        """
        테넌트별 스키마명 생성
        
        Args:
            tenant_id: 테넌트 ID
            platform: 플랫폼 (freshdesk, zendesk 등)
            
        Returns:
            str: 스키마명 (예: tenant_company_a_freshdesk)
        """
        # 안전한 스키마명 생성 (특수문자 제거)
        safe_tenant_id = "".join(c if c.isalnum() else "_" for c in tenant_id.lower())
        return f"{self.schema_prefix}{safe_tenant_id}_{platform}"
    
    def get_tenant_sqlite_path(self, tenant_id: str, platform: str) -> str:
        """
        개발환경: 테넌트별 SQLite 파일 경로
        
        Args:
            tenant_id: 테넌트 ID  
            platform: 플랫폼
            
        Returns:
            str: SQLite 파일 경로
        """
        backend_dir = Path(__file__).parent.parent
        safe_tenant_id = "".join(c if c.isalnum() else "_" for c in tenant_id.lower())
        return str(backend_dir / f"data_{safe_tenant_id}_{platform}.db")
    
    def create_tenant_schema(self, tenant_id: str, platform: str) -> bool:
        """
        테넌트용 스키마 생성 (PostgreSQL)
        
        Args:
            tenant_id: 테넌트 ID
            platform: 플랫폼
            
        Returns:
            bool: 성공 여부
        """
        if not self.settings.DATABASE_URL:
            # 개발환경에서는 SQLite 사용 (자동 생성)
            return True
        
        schema_name = self.get_tenant_schema_name(tenant_id, platform)
        
        try:
            # TODO: PostgreSQL 연결 및 스키마 생성
            # import psycopg2
            # conn = psycopg2.connect(self.settings.DATABASE_URL)
            # cursor = conn.cursor()
            # cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
            # 
            # # 테이블 생성 (tickets, conversations, documents, attachments, collection_jobs)
            # self._create_tenant_tables(cursor, schema_name)
            # 
            # conn.commit()
            # conn.close()
            print(f"PostgreSQL 스키마 생성: {schema_name}")
            return True
        except Exception as e:
            print(f"스키마 생성 실패 ({schema_name}): {e}")
            return False
    
    def _create_tenant_tables(self, cursor, schema_name: str):
        """테넌트 스키마에 테이블 생성"""
        # 현재 core/database/database.py의 테이블 구조를 사용
        tables = [
            f"""                CREATE TABLE IF NOT EXISTS {schema_name}.tickets (
                    id SERIAL PRIMARY KEY,
                    original_id VARCHAR(50) NOT NULL,
                    subject TEXT,
                    description TEXT,
                    status VARCHAR(20),
                    priority VARCHAR(20),
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP,
                    created_at_platform TIMESTAMP,
                    updated_at_platform TIMESTAMP,
                    tenant_id VARCHAR(50) NOT NULL,
                    platform VARCHAR(20) NOT NULL
                )
            """,
            f"""                CREATE TABLE IF NOT EXISTS {schema_name}.conversations (
                    id SERIAL PRIMARY KEY,
                    original_id VARCHAR(50) NOT NULL,
                    ticket_id VARCHAR(50),
                    user_id VARCHAR(50),
                    body_text TEXT,
                    from_email VARCHAR(255),
                    to_emails TEXT,
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP,
                    tenant_id VARCHAR(50) NOT NULL,
                    platform VARCHAR(20) NOT NULL
                )
            """,
            f"""                CREATE TABLE IF NOT EXISTS {schema_name}.documents (
                    id SERIAL PRIMARY KEY,
                    original_id VARCHAR(50) NOT NULL,
                    title TEXT,
                    description TEXT,
                    content TEXT,
                    folder_id VARCHAR(50),
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP,
                    tenant_id VARCHAR(50) NOT NULL,
                    platform VARCHAR(20) NOT NULL
                )
            """,
            f"""                CREATE TABLE IF NOT EXISTS {schema_name}.attachments (
                    id SERIAL PRIMARY KEY,
                    original_id VARCHAR(50) NOT NULL,
                    name VARCHAR(255),
                    content_type VARCHAR(100),
                    size INTEGER,
                    download_url TEXT,
                    parent_type VARCHAR(20),
                    parent_original_id VARCHAR(50),
                    tenant_id VARCHAR(50) NOT NULL,
                    platform VARCHAR(20) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """,
            f"""                CREATE TABLE IF NOT EXISTS {schema_name}.collection_jobs (
                    id SERIAL PRIMARY KEY,
                    job_id VARCHAR(50) UNIQUE NOT NULL,
                    tenant_id VARCHAR(50) NOT NULL,
                    platform VARCHAR(20) NOT NULL,
                    status VARCHAR(20) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """,
            f"""                CREATE TABLE IF NOT EXISTS {schema_name}.settings (
                    id SERIAL PRIMARY KEY,
                    tenant_id VARCHAR(50) NOT NULL,
                    platform VARCHAR(20) NOT NULL,
                    key VARCHAR(255) NOT NULL,
                    value TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """
        ]
        
        for table in tables:
            cursor.execute(table)
    
    # 멀티테넌트 데이터베이스 접근 예시

    def get_database_connection(tenant_id: str, platform: str):
        """
        테넌트별 데이터베이스 연결 정보 반환
        """
        db_manager = get_db_manager()
        
        if settings.DATABASE_URL:
            # 운영환경: PostgreSQL + 스키마별 격리
            schema_name = db_manager.get_tenant_schema_name(tenant_id, platform)
            # schema_name = "tenant_company_a_freshdesk"
            
            return {
                "url": settings.DATABASE_URL,
                "schema": schema_name,
                "query_prefix": f"SET search_path TO {schema_name};"
            }
        else:
            # 개발환경: SQLite + 파일별 격리  
            sqlite_path = db_manager.get_tenant_sqlite_path(tenant_id, platform)
            # sqlite_path = "/backend/data_company_a_freshdesk.db"
            
            return {
                "url": f"sqlite:///{sqlite_path}",
                "schema": None,
                "query_prefix": ""
            }


    def insert_ticket(tenant_id: str, platform: str, ticket_data: dict):
        """
        테넌트별 티켓 삽입 예시
        """
        db_info = get_database_connection(tenant_id, platform)
        
        if settings.DATABASE_URL:
            # PostgreSQL: 스키마 지정
            with psycopg2.connect(db_info["url"]) as conn:
                cursor = conn.cursor()
                cursor.execute(db_info["query_prefix"])  # SET search_path
                
                cursor.execute("""
                    INSERT INTO tickets (original_id, subject, description) 
                    VALUES (%s, %s, %s)
                """, (ticket_data["id"], ticket_data["subject"], ticket_data["description"]))
                
                conn.commit()
        else:
            # SQLite: 파일별 격리
            with sqlite3.connect(db_info["url"].replace("sqlite:///", "")) as conn:
                conn.execute("""
                    INSERT INTO tickets (original_id, subject, description)
                    VALUES (?, ?, ?)  
                """, (ticket_data["id"], ticket_data["subject"], ticket_data["description"]))
                
                conn.commit()


    def get_company_tickets(tenant_id: str, platform: str):
        """
        특정 회사의 티켓 조회
        """
        db_info = get_database_connection(tenant_id, platform)
        
        if settings.DATABASE_URL:
            # PostgreSQL: 해당 회사 스키마의 tickets 테이블만 조회
            with psycopg2.connect(db_info["url"]) as conn:
                cursor = conn.cursor()
                cursor.execute(db_info["query_prefix"])
                
                cursor.execute("SELECT * FROM tickets ORDER BY created_at DESC")
                return cursor.fetchall()
        else:
            # SQLite: 해당 회사 파일의 tickets 테이블만 조회
            with sqlite3.connect(db_info["url"].replace("sqlite:///", "")) as conn:
                cursor = conn.execute("SELECT * FROM tickets ORDER BY created_at DESC")
                return cursor.fetchall()


class GlobalLLMKeysManager:
    """
    전역 LLM API 키 관리 클래스
    
    전략:
    - 개발환경: 환경변수에서 로드
    - 운영환경: AWS Secrets Manager에서 로드
    - 모든 테넌트가 공유하는 LLM API 키들 관리
    """
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.llm_keys_cache: Dict[str, str] = {}
        self.secrets_client = None
        self._init_aws_client()
    
    def _init_aws_client(self):
        """AWS Secrets Manager 클라이언트 초기화"""
        try:
            if self.settings.AWS_ACCESS_KEY_ID and self.settings.AWS_SECRET_ACCESS_KEY:
                self.secrets_client = boto3.client(
                    'secretsmanager',
                    region_name=self.settings.AWS_REGION,
                    aws_access_key_id=self.settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=self.settings.AWS_SECRET_ACCESS_KEY
                )
        except Exception as e:
            print(f"AWS Secrets Manager 클라이언트 초기화 실패: {e}")
            self.secrets_client = None
    
    def get_llm_api_key(self, provider: str) -> Optional[str]:
        """
        LLM 제공자별 API 키 조회
        
        우선순위:
        1. 캐시
        2. AWS Secrets Manager (운영환경)
        3. 환경변수 (개발환경)
        
        Args:
            provider: LLM 제공자 (anthropic, openai, google, perplexity, deepseek, openrouter)
            
        Returns:
            Optional[str]: API 키 또는 None
        """
        # 1. 캐시에서 조회
        if provider in self.llm_keys_cache:
            return self.llm_keys_cache[provider]
        
        # 2. AWS Secrets Manager에서 조회 (운영환경)
        secrets_key = self._load_llm_key_from_secrets(provider)
        if secrets_key:
            self.llm_keys_cache[provider] = secrets_key
            return secrets_key
        
        # 3. 환경변수에서 조회 (개발환경)
        env_key = self._get_llm_key_from_env(provider)
        if env_key:
            self.llm_keys_cache[provider] = env_key
            return env_key
        
        return None
    
    def _load_llm_key_from_secrets(self, provider: str) -> Optional[str]:
        """AWS Secrets Manager에서 LLM API 키 로드"""
        if not self.secrets_client:
            return None
        
        secret_name = "global-llm-keys"
        
        try:
            response = self.secrets_client.get_secret_value(SecretId=secret_name)
            secret_data = json.loads(response['SecretString'])
            
            # 제공자별 키 매핑
            key_mapping = {
                "anthropic": "anthropic_api_key",
                "openai": "openai_api_key", 
                "google": "google_api_key",
                "gemini": "google_api_key",  # 별칭
                "perplexity": "perplexity_api_key",
                "deepseek": "deepseek_api_key",
                "openrouter": "openrouter_api_key"
            }
            
            secret_key = key_mapping.get(provider.lower())
            if secret_key and secret_key in secret_data:
                return secret_data[secret_key]
                
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                print(f"전역 LLM 키 시크릿을 찾을 수 없음: {secret_name}")
            else:
                print(f"AWS Secrets Manager 오류 (LLM 키): {e}")
        except Exception as e:
            print(f"LLM 키 시크릿 파싱 오류: {e}")
        
        return None
    
    def _get_llm_key_from_env(self, provider: str) -> Optional[str]:
        """환경변수에서 LLM API 키 조회"""
        env_mapping = {
            "anthropic": self.settings.ANTHROPIC_API_KEY,
            "openai": self.settings.OPENAI_API_KEY,
            "google": self.settings.GOOGLE_API_KEY,
            "gemini": self.settings.GOOGLE_API_KEY,  # 별칭
            "perplexity": self.settings.PERPLEXITY_API_KEY,
            "deepseek": self.settings.DEEPSEEK_API_KEY,
            "openrouter": self.settings.OPENROUTER_API_KEY
        }
        
        return env_mapping.get(provider.lower())
    
    def save_llm_keys_to_secrets(self, api_keys: Dict[str, str]) -> bool:
        """
        전역 LLM API 키들을 AWS Secrets Manager에 저장
        
        Args:
            api_keys: 저장할 API 키들 딕셔너리
                     {"anthropic_api_key": "sk-...", "openai_api_key": "sk-..."}
            
        Returns:
            bool: 성공 여부
        """
        if not self.secrets_client:
            return False
        
        secret_name = "global-llm-keys"
        
        try:
            # 시크릿이 존재하면 업데이트, 없으면 생성
            try:
                self.secrets_client.update_secret(
                    SecretId=secret_name,
                    SecretString=json.dumps(api_keys)
                )
            except ClientError as e:
                if e.response['Error']['Code'] == 'ResourceNotFoundException':
                    # 시크릿이 없으면 생성
                    self.secrets_client.create_secret(
                        Name=secret_name,
                        SecretString=json.dumps(api_keys),
                        Description="전역 LLM API 키들 (모든 테넌트 공유)"
                    )
                else:
                    raise
            
            # 캐시 업데이트
            provider_mapping = {
                "anthropic_api_key": "anthropic",
                "openai_api_key": "openai",
                "google_api_key": "google", 
                "perplexity_api_key": "perplexity",
                "deepseek_api_key": "deepseek",
                "openrouter_api_key": "openrouter"
            }
            
            for secret_key, api_key in api_keys.items():
                provider = provider_mapping.get(secret_key)
                if provider:
                    self.llm_keys_cache[provider] = api_key
            
            return True
            
        except Exception as e:
            print(f"전역 LLM 키 저장 실패: {e}")
            return False


# 멀티테넌트 DB 관리자 싱글톤
_db_manager: Optional[MultiTenantDatabaseManager] = None

def get_db_manager() -> MultiTenantDatabaseManager:
    """멀티테넌트 DB 관리자 인스턴스 반환"""
    global _db_manager
    if _db_manager is None:
        _db_manager = MultiTenantDatabaseManager(get_settings())
    return _db_manager


# 멀티테넌트 설정 관리자 싱글톤
_tenant_manager: Optional[MultiTenantConfigManager] = None

def get_tenant_manager() -> MultiTenantConfigManager:
    """멀티테넌트 설정 관리자 인스턴스 반환"""
    global _tenant_manager
    if _tenant_manager is None:
        _tenant_manager = MultiTenantConfigManager(get_settings())
    return _tenant_manager


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
