# 🔄 SQLite → PostgreSQL 마이그레이션 가이드

## ⚠️ 중요: 완전 자동 호환은 아닙니다!

SQLite와 PostgreSQL은 **유사하지만 다른 데이터베이스**이므로, 마이그레이션 시 **코드 수정이 필요**합니다.

## 🔧 필요한 코드 수정 사항

### 1. **데이터베이스 연결 설정 변경**

#### 현재 (SQLite)
```python
# backend/core/database/database.py
class SQLiteDatabase:
    def __init__(self, company_id: str, platform: str = "freshdesk"):
        db_name = f"{company_id}_{platform}_data.db"
        self.db_path = Path(__file__).parent.parent / "data" / db_name
        self.connection = sqlite3.connect(self.db_path)
```

#### 변경 후 (PostgreSQL)
```python
# backend/core/database/database.py
import psycopg2
from sqlalchemy import create_engine

class PostgreSQLDatabase:
    def __init__(self, company_id: str, platform: str = "freshdesk"):
        # 단일 DB + company_id로 구분
        self.company_id = company_id
        self.platform = platform
        database_url = os.getenv('DATABASE_URL')
        self.engine = create_engine(database_url)
```

### 2. **SQL 문법 차이점 수정**

#### 날짜/시간 처리
```python
# SQLite (현재)
cursor.execute("SELECT * FROM tickets WHERE created_at > date('now', '-30 days')")

# PostgreSQL (변경 필요)
cursor.execute("SELECT * FROM tickets WHERE created_at > CURRENT_DATE - INTERVAL '30 days'")
```

#### JSON 필드 처리
```python
# SQLite (현재)
cursor.execute("UPDATE companies SET features = ? WHERE id = ?", [json.dumps(features), company_id])

# PostgreSQL (변경 필요)  
cursor.execute("UPDATE companies SET features = %s WHERE id = %s", [json.dumps(features), company_id])
```

#### LIMIT/OFFSET 구문
```python
# SQLite (현재)
cursor.execute("SELECT * FROM tickets LIMIT ? OFFSET ?", [limit, offset])

# PostgreSQL (변경 필요)
cursor.execute("SELECT * FROM tickets LIMIT %s OFFSET %s", [limit, offset])
```

### 3. **스키마 생성 스크립트 분리**

#### SQLite 버전
```python
# backend/core/database/sqlite_schema.py
def create_sqlite_tables(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name TEXT NOT NULL,
            features TEXT NOT NULL,  -- JSON 문자열
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
```

#### PostgreSQL 버전
```python
# backend/core/database/postgresql_schema.py
def create_postgresql_tables(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS companies (
            id SERIAL PRIMARY KEY,
            company_name VARCHAR(255) NOT NULL,
            features JSONB NOT NULL,  -- JSONB 타입
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
```

### 4. **데이터 타입 매핑 수정**

```python
# backend/core/database/type_mapper.py
class DatabaseTypeMapper:
    def get_json_type(self, db_type):
        if db_type == 'sqlite':
            return 'TEXT'  # JSON을 문자열로 저장
        elif db_type == 'postgresql':
            return 'JSONB'  # 네이티브 JSON 타입
    
    def get_timestamp_type(self, db_type):
        if db_type == 'sqlite':
            return 'TEXT'
        elif db_type == 'postgresql':
            return 'TIMESTAMP'
```

### 5. **ORM 모델 수정 (SQLAlchemy 사용 시)**

```python
# backend/core/models/base.py
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Company(Base):
    __tablename__ = 'companies'
    
    id = Column(Integer, primary_key=True)
    company_name = Column(String(255), nullable=False)
    
    # DB별 조건부 타입 사용
    if DATABASE_TYPE == 'postgresql':
        features = Column(JSONB)  # PostgreSQL
    else:
        features = Column(Text)   # SQLite
    
    created_at = Column(DateTime, default=datetime.utcnow)
```

### 6. **데이터 마이그레이션 스크립트**

```python
# scripts/migrate_sqlite_to_postgresql.py
import sqlite3
import psycopg2
import json
from datetime import datetime

class SQLiteToPostgreSQLMigrator:
    def __init__(self, sqlite_path, postgresql_url):
        self.sqlite_conn = sqlite3.connect(sqlite_path)
        self.pg_conn = psycopg2.connect(postgresql_url)
    
    def migrate_companies(self):
        """회사 데이터 이전"""
        sqlite_cursor = self.sqlite_conn.cursor()
        pg_cursor = self.pg_conn.cursor()
        
        # SQLite에서 데이터 조회
        sqlite_cursor.execute("SELECT * FROM companies")
        companies = sqlite_cursor.fetchall()
        
        for company in companies:
            # JSON 문자열을 JSONB로 변환
            features = json.loads(company[3]) if company[3] else {}
            
            # PostgreSQL에 삽입
            pg_cursor.execute("""
                INSERT INTO companies (company_name, features, created_at)
                VALUES (%s, %s, %s)
            """, [company[1], json.dumps(features), company[4]])
        
        self.pg_conn.commit()
    
    def migrate_all_data(self):
        """전체 데이터 마이그레이션"""
        self.migrate_companies()
        self.migrate_tickets()
        self.migrate_agents()
        # ... 다른 테이블들
```

### 7. **환경별 설정 관리**

```python
# backend/core/config.py
import os

class DatabaseConfig:
    def __init__(self):
        self.database_url = os.getenv('DATABASE_URL')
        
    def get_database_type(self):
        if self.database_url and 'postgresql' in self.database_url:
            return 'postgresql'
        else:
            return 'sqlite'
    
    def get_connection_params(self, company_id):
        if self.get_database_type() == 'postgresql':
            return {
                'url': self.database_url,
                'company_id': company_id  # WHERE 절에서 필터링
            }
        else:
            return {
                'path': f'./data/{company_id}_freshdesk_data.db'
            }
```

### 8. **쿼리 추상화 레이어**

```python
# backend/core/database/query_builder.py
class QueryBuilder:
    def __init__(self, db_type):
        self.db_type = db_type
    
    def get_tickets_query(self, company_id, limit=100):
        if self.db_type == 'postgresql':
            return """
                SELECT * FROM tickets 
                WHERE company_id = %s 
                ORDER BY created_at DESC 
                LIMIT %s
            """, [company_id, limit]
        else:
            return """
                SELECT * FROM tickets 
                ORDER BY created_at DESC 
                LIMIT ?
            """, [limit]  # SQLite는 company_id 필터링 불필요 (별도 DB)
    
    def get_json_extract(self, field, key):
        if self.db_type == 'postgresql':
            return f"{field}->'{key}'"  # JSONB 연산자
        else:
            return f"JSON_EXTRACT({field}, '$.{key}')"  # SQLite JSON 함수
```

## 🚀 실제 마이그레이션 단계

### 1단계: 코드 추상화 (개발 중)
```python
# 현재 개발하면서 점진적으로 적용
def get_database():
    if DATABASE_TYPE == 'postgresql':
        return PostgreSQLDatabase()
    else:
        return SQLiteDatabase()
```

### 2단계: 스키마 검증 (배포 전)
```bash
# PostgreSQL 스키마 테스트
python scripts/test_postgresql_schema.py
```

### 3단계: 데이터 마이그레이션 (배포 시)
```bash
# 모든 SQLite 파일을 PostgreSQL로 이전
python scripts/migrate_all_companies.py
```

### 4단계: 설정 전환 (배포 시)
```bash
# 환경변수 변경
DATABASE_URL="postgresql://user:pass@rds.amazonaws.com/saas_db"
```

## 💡 권장 개발 전략

### **지금 할 일 (개발 단계)**
1. **ORM 사용**: SQLAlchemy 등으로 DB 무관한 코드 작성
2. **추상화 레이어**: 데이터베이스 타입별 클래스 분리
3. **환경변수 준비**: DATABASE_URL 기반 자동 전환 로직

### **나중에 할 일 (배포 전)**
1. **마이그레이션 스크립트 작성**: SQLite → PostgreSQL 데이터 이전
2. **통합 테스트**: PostgreSQL 환경에서 전체 기능 테스트
3. **성능 최적화**: PostgreSQL 전용 인덱스/쿼리 튜닝

## ⚠️ 주의사항

### **완전 자동 호환되지 않는 부분**
- ❌ SQL 문법 차이 (날짜, JSON, 파라미터 바인딩)
- ❌ 데이터 타입 차이 (TEXT vs VARCHAR, JSONB vs TEXT)
- ❌ 멀티테넌트 구조 차이 (파일 분리 vs 테이블 필터링)

### **비교적 쉽게 해결되는 부분**
- ✅ 기본 CRUD 로직 (ORM 사용 시)
- ✅ 비즈니스 로직 (데이터베이스 무관)
- ✅ API 엔드포인트 (데이터 레이어만 변경)

## 🎯 결론

**"호환이 잘된다"** = ✅ **구조적으로 유사하여 마이그레이션이 가능**
**"코드 수정 불필요"** = ❌ **일부 데이터베이스 레이어 코드는 수정 필요**

**하지만 걱정하지 마세요!** 
- 전체 코드의 80-90%는 그대로 사용 가능
- 수정이 필요한 부분은 주로 데이터베이스 연결/쿼리 부분만
- ORM 사용 시 수정 범위가 크게 줄어듦
