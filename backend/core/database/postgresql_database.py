"""
PostgreSQL 기반 멀티테넌트 데이터베이스 관리
스키마 기반 테넌트 분리 및 멀티플랫폼 지원
"""

import psycopg2
import psycopg2.extras
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import os

logger = logging.getLogger(__name__)

class PostgreSQLDatabase:
    """PostgreSQL 스키마 기반 멀티테넌트 데이터베이스 관리"""
    
    def __init__(self, company_id: str, platform: str = "freshdesk"):
        """
        PostgreSQL 멀티테넌트 데이터베이스 초기화
        
        Args:
            company_id: 회사 ID (스키마명으로 사용)
            platform: 플랫폼명 (테이블 접두사로 사용)
        """
        if not company_id:
            raise ValueError("company_id는 필수 매개변수입니다")
            
        # 스키마명 정규화 (PostgreSQL 네이밍 규칙 준수)
        self.company_id = self._normalize_schema_name(company_id)
        self.platform = platform.lower()
        self.schema_name = f"tenant_{self.company_id}"
        
        # 연결 정보
        self.connection = None
        self._tables_created = False
        
        # PostgreSQL 연결 설정
        self.db_config = {
            'host': os.getenv('POSTGRES_HOST', 'localhost'),
            'port': os.getenv('POSTGRES_PORT', '5432'),
            'database': os.getenv('POSTGRES_DB', 'saas_platform'),
            'user': os.getenv('POSTGRES_USER', 'postgres'),
            'password': os.getenv('POSTGRES_PASSWORD', 'password')
        }
        
        logger.info(f"PostgreSQL 멀티테넌트 DB 초기화: schema={self.schema_name}, platform={self.platform}")
    
    def _normalize_schema_name(self, company_id: str) -> str:
        """스키마명 정규화 (PostgreSQL 규칙 준수)"""
        # 소문자 변환, 특수문자 제거, 언더스코어로 대체
        import re
        normalized = re.sub(r'[^a-zA-Z0-9_]', '_', company_id.lower())
        # 숫자로 시작하면 접두사 추가
        if normalized[0].isdigit():
            normalized = f"c_{normalized}"
        return normalized
    
    def connect(self):
        """PostgreSQL 연결"""
        try:
            self.connection = psycopg2.connect(**self.db_config)
            self.connection.autocommit = False
            
            # 스키마 생성 (존재하지 않을 경우)
            self._ensure_schema_exists()
            
            # 스키마를 기본 검색 경로로 설정
            with self.connection.cursor() as cursor:
                cursor.execute(f"SET search_path TO {self.schema_name}, public")
                self.connection.commit()
            
            logger.info(f"PostgreSQL 연결 완료: {self.db_config['host']}:{self.db_config['port']} / {self.schema_name}")
            
            # 테이블 생성
            if not self._tables_created:
                self.create_tables()
                
        except Exception as e:
            logger.error(f"PostgreSQL 연결 실패: {e}")
            raise
    
    def _ensure_schema_exists(self):
        """스키마 존재 확인 및 생성"""
        with self.connection.cursor() as cursor:
            # 스키마 존재 확인
            cursor.execute("""
                SELECT schema_name FROM information_schema.schemata 
                WHERE schema_name = %s
            """, (self.schema_name,))
            
            if not cursor.fetchone():
                # 스키마 생성
                cursor.execute(f"CREATE SCHEMA {self.schema_name}")
                self.connection.commit()
                logger.info(f"스키마 생성 완료: {self.schema_name}")
    
    def disconnect(self):
        """연결 해제"""
        if self.connection:
            self.connection.close()
            self.connection = None
            logger.info(f"PostgreSQL 연결 해제: {self.schema_name}")
    
    def create_tables(self):
        """멀티테넌트 테이블 생성"""
        if not self.connection:
            self.connect()
        
        with self.connection.cursor() as cursor:
            # =====================================================
            # 🏢 SaaS 메타데이터 테이블 (public 스키마)
            # =====================================================
            
            # 테넌트 정보 테이블 (모든 테넌트 공통)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS public.tenants (
                    id SERIAL PRIMARY KEY,
                    company_id VARCHAR(100) UNIQUE NOT NULL,
                    schema_name VARCHAR(100) UNIQUE NOT NULL,
                    company_name VARCHAR(255) NOT NULL,
                    domain VARCHAR(255) UNIQUE NOT NULL,
                    subscription_plan_id INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE
                )
            """)
            
            # 플랫폼 정보 테이블 (공통)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS public.platforms (
                    id SERIAL PRIMARY KEY,
                    platform_name VARCHAR(50) UNIQUE NOT NULL,
                    display_name VARCHAR(100) NOT NULL,
                    api_config JSONB,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 테넌트-플랫폼 연결 테이블
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS public.tenant_platforms (
                    id SERIAL PRIMARY KEY,
                    tenant_id INTEGER REFERENCES public.tenants(id),
                    platform_id INTEGER REFERENCES public.platforms(id),
                    platform_config JSONB,
                    is_enabled BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(tenant_id, platform_id)
                )
            """)
            
            # =====================================================
            # 📊 테넌트별 통합 데이터 테이블
            # =====================================================
            
            # 통합 객체 테이블 (테넌트 스키마 내)
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.schema_name}.integrated_objects (
                    id SERIAL PRIMARY KEY,
                    original_id VARCHAR(255) NOT NULL,
                    platform VARCHAR(50) NOT NULL,
                    object_type VARCHAR(50) NOT NULL,
                    original_data JSONB NOT NULL,
                    integrated_content TEXT,
                    summary TEXT,
                    metadata JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(platform, object_type, original_id)
                )
            """)
            
            # 진행 로그 테이블
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.schema_name}.progress_logs (
                    id SERIAL PRIMARY KEY,
                    job_id VARCHAR(255) NOT NULL,
                    message TEXT NOT NULL,
                    percentage NUMERIC(5,2) NOT NULL,
                    step INTEGER NOT NULL,
                    total_steps INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(job_id, step)
                )
            """)
            
            # =====================================================
            # 📊 인덱스 생성
            # =====================================================
            
            # 통합 객체 인덱스
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{self.schema_name}_integrated_platform 
                ON {self.schema_name}.integrated_objects(platform)
            """)
            
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{self.schema_name}_integrated_type 
                ON {self.schema_name}.integrated_objects(object_type)
            """)
            
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{self.schema_name}_integrated_created 
                ON {self.schema_name}.integrated_objects(created_at)
            """)
            
            # JSON 인덱스 (PostgreSQL 특화)
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{self.schema_name}_metadata_gin 
                ON {self.schema_name}.integrated_objects USING GIN (metadata)
            """)
            
            # 진행 로그 인덱스
            cursor.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{self.schema_name}_progress_job 
                ON {self.schema_name}.progress_logs(job_id)
            """)
            
            self.connection.commit()
            logger.info(f"테넌트 테이블 생성 완료: {self.schema_name}")
            self._tables_created = True
    
    def register_tenant(self, tenant_data: Dict[str, Any]) -> int:
        """테넌트 등록 (public.tenants 테이블)"""
        if not self.connection:
            self.connect()
        
        with self.connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO public.tenants (
                    company_id, schema_name, company_name, domain, subscription_plan_id
                ) VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (company_id) DO UPDATE SET
                    company_name = EXCLUDED.company_name,
                    domain = EXCLUDED.domain,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id
            """, (
                self.company_id,
                self.schema_name,
                tenant_data.get('company_name'),
                tenant_data.get('domain'),
                tenant_data.get('subscription_plan_id')
            ))
            
            tenant_id = cursor.fetchone()[0]
            self.connection.commit()
            
            logger.info(f"테넌트 등록 완료: {self.company_id} (ID: {tenant_id})")
            return tenant_id
    
    def insert_integrated_object(self, integrated_data: Dict[str, Any]) -> int:
        """통합 객체 데이터 삽입"""
        if not self.connection:
            self.connect()
        
        with self.connection.cursor() as cursor:
            cursor.execute(f"""
                INSERT INTO {self.schema_name}.integrated_objects (
                    original_id, platform, object_type, original_data,
                    integrated_content, summary, metadata
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (platform, object_type, original_id) DO UPDATE SET
                    original_data = EXCLUDED.original_data,
                    integrated_content = EXCLUDED.integrated_content,
                    summary = EXCLUDED.summary,
                    metadata = EXCLUDED.metadata,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id
            """, (
                str(integrated_data.get('original_id')),
                self.platform,
                integrated_data.get('object_type'),
                json.dumps(integrated_data.get('original_data', {})),
                integrated_data.get('integrated_content'),
                integrated_data.get('summary'),
                json.dumps(integrated_data.get('metadata', {}))
            ))
            
            object_id = cursor.fetchone()[0]
            self.connection.commit()
            return object_id
    
    def get_integrated_objects_by_type(self, object_type: str, platform: str = None) -> List[Dict[str, Any]]:
        """타입별 통합 객체 조회"""
        if not self.connection:
            self.connect()
        
        platform = platform or self.platform
        
        with self.connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute(f"""
                SELECT * FROM {self.schema_name}.integrated_objects 
                WHERE platform = %s AND object_type = %s
                ORDER BY created_at DESC
            """, (platform, object_type))
            
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def search_integrated_content(self, query: str, object_types: List[str] = None, platform: str = None) -> List[Dict[str, Any]]:
        """통합 콘텐츠 검색 (PostgreSQL 전문 검색 활용)"""
        if not self.connection:
            self.connect()
        
        platform = platform or self.platform
        
        with self.connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            base_query = f"""
                SELECT *, 
                       ts_rank(to_tsvector('english', integrated_content), plainto_tsquery('english', %s)) as rank
                FROM {self.schema_name}.integrated_objects 
                WHERE platform = %s 
                AND to_tsvector('english', integrated_content) @@ plainto_tsquery('english', %s)
            """
            
            params = [query, platform, query]
            
            if object_types:
                placeholders = ','.join(['%s'] * len(object_types))
                base_query += f" AND object_type IN ({placeholders})"
                params.extend(object_types)
            
            base_query += " ORDER BY rank DESC, updated_at DESC"
            
            cursor.execute(base_query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    def clear_tenant_data(self, platform: str = None):
        """테넌트 데이터 삭제"""
        if not self.connection:
            self.connect()
        
        with self.connection.cursor() as cursor:
            if platform:
                cursor.execute(f"""
                    DELETE FROM {self.schema_name}.integrated_objects WHERE platform = %s
                """, (platform,))
            else:
                cursor.execute(f"DELETE FROM {self.schema_name}.integrated_objects")
                cursor.execute(f"DELETE FROM {self.schema_name}.progress_logs")
            
            self.connection.commit()
            logger.info(f"테넌트 데이터 삭제 완료: {self.schema_name}")
    
    def count_integrated_objects(self) -> int:
        """통합 객체 총 개수 반환"""
        try:
            self.connect()
            with self.connection.cursor() as cursor:
                cursor.execute(f"SELECT COUNT(*) FROM {self.schema_name}.integrated_objects")
                count = cursor.fetchone()[0]
                return count
        except Exception as e:
            logger.error(f"통합 객체 개수 조회 오류: {e}")
            return 0
        finally:
            self.disconnect()
    
    def count_integrated_objects_by_type(self, object_type: str) -> int:
        """특정 타입의 통합 객체 개수 반환"""
        try:
            self.connect()
            with self.connection.cursor() as cursor:
                cursor.execute(
                    f"SELECT COUNT(*) FROM {self.schema_name}.integrated_objects WHERE object_type = %s",
                    (object_type,)
                )
                count = cursor.fetchone()[0]
                return count
        except Exception as e:
            logger.error(f"{object_type} 타입 객체 개수 조회 오류: {e}")
            return 0
        finally:
            self.disconnect()
    
    def get_integrated_objects_statistics(self) -> Dict[str, Any]:
        """통합 객체 통계 정보 반환"""
        try:
            self.connect()
            with self.connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                # 전체 개수
                cursor.execute(f"SELECT COUNT(*) FROM {self.schema_name}.integrated_objects")
                total_count = cursor.fetchone()[0]
                
                # 타입별 개수
                cursor.execute(f"""
                    SELECT object_type, COUNT(*) as count 
                    FROM {self.schema_name}.integrated_objects 
                    GROUP BY object_type
                """)
                type_counts = {row['object_type']: row['count'] for row in cursor.fetchall()}
                
                # 최근 생성된 객체들
                cursor.execute(f"""
                    SELECT object_type, MAX(created_at) as latest_created
                    FROM {self.schema_name}.integrated_objects 
                    GROUP BY object_type
                """)
                latest_by_type = {row['object_type']: row['latest_created'] for row in cursor.fetchall()}
                
                return {
                    'total_count': total_count,
                    'type_counts': type_counts,
                    'latest_by_type': latest_by_type,
                    'tenant_id': self.company_id,
                    'platform': self.platform,
                    'schema_name': self.schema_name
                }
                
        except Exception as e:
            logger.error(f"통합 객체 통계 조회 오류: {e}")
            return {
                'total_count': 0,
                'type_counts': {},
                'latest_by_type': {},
                'tenant_id': self.company_id,
                'platform': self.platform,
                'schema_name': self.schema_name
            }
        finally:
            self.disconnect()


def get_postgresql_database(company_id: str, platform: str = "freshdesk") -> PostgreSQLDatabase:
    """PostgreSQL 멀티테넌트 데이터베이스 인스턴스 반환"""
    return PostgreSQLDatabase(company_id, platform)


# 테넌트 관리 유틸리티
class TenantManager:
    """테넌트 관리 유틸리티"""
    
    @staticmethod
    def create_tenant(company_id: str, tenant_data: Dict[str, Any]) -> PostgreSQLDatabase:
        """새 테넌트 생성"""
        db = PostgreSQLDatabase(company_id)
        db.connect()
        db.register_tenant(tenant_data)
        return db
    
    @staticmethod
    def list_tenants() -> List[Dict[str, Any]]:
        """전체 테넌트 목록 조회"""
        # 임시 연결로 public.tenants 조회
        from .postgresql_database import PostgreSQLDatabase
        
        temp_db = PostgreSQLDatabase("temp")
        temp_db.connect()
        
        with temp_db.connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
            cursor.execute("SELECT * FROM public.tenants WHERE is_active = TRUE ORDER BY created_at")
            tenants = [dict(row) for row in cursor.fetchall()]
        
        temp_db.disconnect()
        return tenants
    
    @staticmethod
    def delete_tenant(company_id: str):
        """테넌트 완전 삭제 (스키마 포함)"""
        db = PostgreSQLDatabase(company_id)
        db.connect()
        
        with db.connection.cursor() as cursor:
            # 스키마 삭제
            cursor.execute(f"DROP SCHEMA IF EXISTS {db.schema_name} CASCADE")
            
            # public.tenants에서 제거
            cursor.execute("DELETE FROM public.tenants WHERE company_id = %s", (company_id,))
            
            db.connection.commit()
        
        db.disconnect()
        logger.info(f"테넌트 완전 삭제 완료: {company_id}")

# 호환성을 위한 alias
PostgreSQLDatabaseManager = PostgreSQLDatabase
