# 🚀 ORM 도입 및 클라우드 전환 준비 계획

## 📊 작업 범위 및 시간 예상

### ⏱️ **시간 예상**
- **🟢 빠른 작업 (1-2일)**: ORM 모델 통합 및 기본 연결
- **🟡 중간 작업 (3-5일)**: 기존 코드 리팩터링 및 테스트
- **🔴 긴 작업 (1-2주)**: 완전한 프로덕션 배포 및 최적화

### 📋 **우선순위별 작업 계획**

## 🚀 **Phase 1: ORM 기반 모델 통합 (1-2일)**

### 1.1 SQLAlchemy 모델을 메인 코드베이스로 이동

```bash
# 현재 위치: backend/tests/db-schema/optimized_models.py
# 이동 위치: backend/core/models/
```

**작업 내용:**
- 기존 ORM 모델을 `backend/core/models/` 디렉토리로 이동
- 통합 객체 스키마에 맞게 모델 업데이트
- `integrated_objects` 모델 추가

### 1.2 데이터베이스 연결 레이어 구현

```python
# backend/core/database/connection.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

class DatabaseManager:
    def __init__(self, database_url: str, is_async: bool = False):
        if is_async:
            self.engine = create_async_engine(database_url)
            self.SessionLocal = sessionmaker(
                self.engine, class_=AsyncSession, expire_on_commit=False
            )
        else:
            self.engine = create_engine(database_url)
            self.SessionLocal = sessionmaker(bind=self.engine)
    
    def get_session(self):
        return self.SessionLocal()
```

### 1.3 환경별 설정 구성

```python
# backend/core/config/database.py
import os
from typing import Optional

class DatabaseConfig:
    def __init__(self):
        self.environment = os.getenv('ENVIRONMENT', 'development')
    
    def get_database_url(self, company_id: Optional[str] = None) -> str:
        if self.environment == 'development':
            # SQLite (기존 방식 유지)
            if company_id:
                return f"sqlite:///./data/{company_id}_freshdesk_data.db"
            return "sqlite:///./data/main.db"
        
        elif self.environment == 'production':
            # PostgreSQL
            return os.getenv('DATABASE_URL', 'postgresql://user:pass@localhost/db')
        
        else:
            raise ValueError(f"Unknown environment: {self.environment}")
```

## 🔄 **Phase 2: 기존 코드 리팩터링 (2-3일)**

### 2.1 Repository 패턴 도입

```python
# backend/core/repositories/integrated_object_repository.py
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from ..models.integrated_objects import IntegratedObject

class IntegratedObjectRepository:
    def __init__(self, session: Session):
        self.session = session
    
    def get_by_company(self, company_id: str, object_type: str = None) -> List[IntegratedObject]:
        query = self.session.query(IntegratedObject).filter_by(company_id=company_id)
        if object_type:
            query = query.filter_by(object_type=object_type)
        return query.all()
    
    def create(self, data: Dict[str, Any]) -> IntegratedObject:
        obj = IntegratedObject(**data)
        self.session.add(obj)
        self.session.commit()
        return obj
    
    def update_summary(self, obj_id: int, summary: str) -> bool:
        obj = self.session.query(IntegratedObject).filter_by(id=obj_id).first()
        if obj:
            obj.summary = summary
            self.session.commit()
            return True
        return False
```

### 2.2 기존 storage.py 코드 업데이트

```python
# backend/core/ingest/storage.py 수정
from ..repositories.integrated_object_repository import IntegratedObjectRepository
from ..database.connection import DatabaseManager

def store_integrated_object_orm(
    integrated_object: Dict[str, Any], 
    company_id: str, 
    platform: str = "freshdesk"
) -> bool:
    """ORM 기반 통합 객체 저장"""
    
    db_manager = DatabaseManager(get_database_url(company_id))
    
    with db_manager.get_session() as session:
        repo = IntegratedObjectRepository(session)
        
        data = {
            'original_id': str(integrated_object.get('id')),
            'company_id': company_id,
            'platform': platform,
            'object_type': integrated_object.get('object_type', 'integrated_ticket'),
            'original_data': integrated_object,
            'integrated_content': integrated_object.get('integrated_text', ''),
            'metadata': create_metadata(integrated_object)
        }
        
        try:
            repo.create(data)
            return True
        except Exception as e:
            logger.error(f"ORM 저장 실패: {e}")
            return False
```

### 2.3 점진적 마이그레이션 레이어

```python
# backend/core/database/migration_layer.py
class MigrationLayer:
    """기존 SQLite와 새 ORM 간의 브릿지"""
    
    def __init__(self, use_orm: bool = False):
        self.use_orm = use_orm
    
    def store_integrated_object(self, *args, **kwargs):
        if self.use_orm:
            return store_integrated_object_orm(*args, **kwargs)
        else:
            return store_integrated_object_to_sqlite(*args, **kwargs)
```

## 🌐 **Phase 3: 클라우드 배포 준비 (3-5일)**

### 3.1 PostgreSQL 스키마 자동 생성

```python
# backend/core/database/schema_manager.py
from sqlalchemy import create_engine
from ..models import Base

class SchemaManager:
    def __init__(self, database_url: str):
        self.engine = create_engine(database_url)
    
    def create_all_tables(self):
        """모든 테이블 생성"""
        Base.metadata.create_all(bind=self.engine)
    
    def drop_all_tables(self):
        """모든 테이블 삭제 (주의!)"""
        Base.metadata.drop_all(bind=self.engine)
    
    def migrate_from_sqlite(self, sqlite_path: str):
        """SQLite에서 PostgreSQL로 데이터 마이그레이션"""
        # 마이그레이션 로직 구현
        pass
```

### 3.2 환경 변수 기반 설정

```bash
# .env.production
ENVIRONMENT=production
DATABASE_URL=postgresql://user:password@rds.amazonaws.com:5432/saas_db
QDRANT_URL=https://qdrant-cluster.aws.com
REDIS_URL=redis://elasticache.aws.com:6379

# .env.development (기존 유지)
ENVIRONMENT=development
DATABASE_URL=sqlite:///./data/main.db
```

### 3.3 Docker 컨테이너 최적화

```dockerfile
# Dockerfile.production
FROM python:3.11-slim

# PostgreSQL 클라이언트 설치
RUN apt-get update && apt-get install -y postgresql-client

# Python 의존성
COPY requirements.txt .
RUN pip install -r requirements.txt

# 애플리케이션 코드
COPY . /app
WORKDIR /app

# 환경별 시작 스크립트
COPY scripts/start-production.sh /start.sh
RUN chmod +x /start.sh

CMD ["/start.sh"]
```

## 🧪 **Phase 4: 테스트 및 검증 (1-2일)**

### 4.1 단위 테스트 추가

```python
# tests/test_orm_integration.py
import pytest
from backend.core.repositories.integrated_object_repository import IntegratedObjectRepository

class TestORMIntegration:
    def test_create_integrated_object(self, test_session):
        repo = IntegratedObjectRepository(test_session)
        
        data = {
            'original_id': 'test_123',
            'company_id': 'test_company',
            'platform': 'freshdesk',
            'object_type': 'integrated_ticket',
            'original_data': {'test': 'data'},
            'integrated_content': 'Test content'
        }
        
        result = repo.create(data)
        assert result.original_id == 'test_123'
        assert result.company_id == 'test_company'
```

### 4.2 통합 테스트

```python
# tests/test_migration_compatibility.py
class TestMigrationCompatibility:
    def test_sqlite_to_orm_compatibility(self):
        """SQLite 기존 코드와 ORM 코드 호환성 테스트"""
        pass
    
    def test_postgresql_schema_creation(self):
        """PostgreSQL 스키마 생성 테스트"""
        pass
```

## 💯 **완료 후 기대 효과**

### 🚀 **즉시 효과**
1. **코드 품질 향상**: 타입 안전성, 자동완성, 리팩터링 지원
2. **개발 속도 증가**: ORM의 강력한 쿼리 빌더와 관계 관리
3. **데이터베이스 추상화**: SQLite ↔ PostgreSQL 손쉬운 전환

### 🌐 **클라우드 배포 준비**
1. **확장성**: PostgreSQL 클러스터링, 읽기 전용 복제본
2. **성능**: 연결 풀링, 쿼리 최적화, 인덱스 관리
3. **모니터링**: 쿼리 성능 추적, 슬로우 쿼리 감지

### 📊 **SaaS 확장성**
1. **멀티테넌트**: Row-Level Security (RLS) 적용 가능
2. **백업/복구**: 자동 백업, 포인트-인-타임 복구
3. **분석**: 실시간 대시보드, 사용량 분석

## 🎯 **권장 진행 방식**

### 🟢 **지금 시작 (빠른 ROI)**
- Phase 1 + Phase 2의 일부
- 기존 기능 유지하면서 ORM 점진 도입
- 개발 환경에서 먼저 검증

### 🟡 **다음 단계 (중장기)**
- Phase 3: 클라우드 배포 준비
- Phase 4: 완전한 검증 및 최적화

### 📋 **실제 시작 코드**

**1일차**: ORM 모델 이동 및 기본 연결
**2일차**: Repository 패턴 도입
**3일차**: 점진적 마이그레이션 레이어 구현
**4일차**: 테스트 및 기존 기능 호환성 검증
**5일차**: 클라우드 배포 설정 준비

## 🤔 **결론: 지금이 적절한 시기인가?**

### ✅ **지금 시작하기 좋은 이유**
1. **기반 작업 완료**: 통합 객체 아키텍처가 안정화됨
2. **ORM 모델 준비**: 이미 완전한 모델이 존재
3. **점진적 적용 가능**: 기존 기능에 영향 없이 도입 가능

### ⚠️ **주의사항**
1. **개발 시간**: 1-2주 정도의 개발 투자 필요
2. **테스트 필요**: 충분한 검증 과정 필요
3. **배포 계획**: 단계적 배포 전략 수립 필요

**추천**: **Phase 1 + Phase 2를 먼저 진행**하여 ORM 기반을 구축하고, **클라우드 배포는 다음 단계**로 계획하는 것이 좋겠습니다. 🚀
