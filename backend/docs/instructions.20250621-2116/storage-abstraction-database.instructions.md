---
applyTo: "**"
---

# 🗄️ 스토리지 추상화 & 데이터베이스 전략 지침서

_AI 참조 최적화 버전 - MVP에서 프로덕션까지 단계별 스토리지 전환_

## 🎯 스토리지 추상화 목표

**개발 환경과 프로덕션 환경의 매끄러운 전환을 위한 추상화 레이어**

- **MVP**: 파일 기반 스토리지 (JSON, 빠른 개발)
- **스테이징**: 하이브리드 (파일 + PostgreSQL 테스트)
- **프로덕션**: 완전 DB 기반 (PostgreSQL + Redis)
- **멀티테넌트**: company_id 기반 완전한 데이터 격리

---

## ⚡ **TL;DR - 핵심 스토리지 전략 요약**

### 💡 **즉시 참조용 핵심 포인트**

**스토리지 전환 단계**:

```
파일 기반 (MVP) → 하이브리드 (스테이징) → PostgreSQL (프로덕션)
```

**추상화 인터페이스**:

```python
StorageInterface
├── FileStorage (개발/테스트)
├── PostgresStorage (프로덕션)
└── HybridStorage (마이그레이션)
```

**환경별 전환**:

- **개발**: `STORAGE_TYPE=file`
- **스테이징**: `STORAGE_TYPE=hybrid`
- **프로덕션**: `STORAGE_TYPE=postgresql`

**멀티테넌트 격리**:

- **파일**: company_id별 디렉터리 분리
- **PostgreSQL**: Row-level Security 적용
- **Redis**: company_id 기반 키 네임스페이스

### 🚨 **스토리지 추상화 주의사항**

- ⚠️ 환경별 자동 전환 → 하드코딩된 스토리지 구현 금지
- ⚠️ 인터페이스 일관성 → 모든 구현체는 동일한 API 제공
- ⚠️ 데이터 마이그레이션 → 무손실 전환을 위한 백업/복구 전략 필수

---

## 🏗️ **스토리지 인터페이스 정의**

### 📋 **StorageInterface 기본 구조**

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime

class StorageInterface(ABC):
    """데이터 저장소 추상화 인터페이스 (멀티플랫폼/멀티테넌트 지원)"""

    @abstractmethod
    async def save_ticket(self, company_id: str, platform: str, ticket_data: Dict) -> str:
        """티켓 데이터 저장"""
        pass

    @abstractmethod
    async def get_ticket(self, company_id: str, platform: str, ticket_id: str) -> Optional[Dict]:
        """티켓 데이터 조회"""
        pass

    @abstractmethod
    async def list_tickets(
        self,
        company_id: str,
        platform: str = None,
        status: str = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """티켓 목록 조회 (필터 지원)"""
        pass

    @abstractmethod
    async def update_processing_status(
        self,
        company_id: str,
        platform: str,
        ticket_id: str,
        status: str
    ) -> bool:
        """처리 상태 업데이트"""
        pass

    @abstractmethod
    async def save_summary(
        self,
        company_id: str,
        platform: str,
        item_id: str,
        summary_data: Dict
    ) -> bool:
        """LLM 요약 결과 저장"""
        pass

    @abstractmethod
    async def get_processing_progress(
        self,
        company_id: str,
        platform: str
    ) -> Dict:
        """처리 진행 상황 조회"""
        pass

    @abstractmethod
    async def save_kb_article(
        self,
        company_id: str,
        platform: str,
        article_data: Dict
    ) -> str:
        """지식베이스 문서 저장"""
        pass

    @abstractmethod
    async def list_companies(self) -> List[str]:
        """등록된 회사 목록 조회"""
        pass

    @abstractmethod
    async def get_platform_stats(self, company_id: str) -> Dict[str, int]:
        """플랫폼별 데이터 통계"""
        pass
```

---

## 📁 **파일 기반 스토리지 (MVP)**

### 🗂️ **FileStorage 완전 구현**

```python
import orjson
from pathlib import Path
import aiofiles
from typing import List, Dict, Optional
import asyncio
from datetime import datetime

class FileStorage(StorageInterface):
    """파일 기반 스토리지 (개발/테스트용)"""

    def __init__(self, base_path: str = "backend/data"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _get_company_path(self, company_id: str, platform: str) -> Path:
        """company_id + platform별 경로 생성"""
        return self.base_path / company_id / platform

    def _get_progress_path(self, company_id: str, platform: str) -> Path:
        """진행 상황 추적 경로"""
        return self.base_path / company_id / platform / "progress"

    async def save_ticket(self, company_id: str, platform: str, ticket_data: Dict) -> str:
        """티켓 데이터를 JSON 파일로 저장"""
        company_path = self._get_company_path(company_id, platform)
        company_path.mkdir(parents=True, exist_ok=True)

        ticket_id = ticket_data.get("ticket_id")
        file_path = company_path / "tickets" / f"{ticket_id}.json"
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # company_id와 platform 자동 태깅
        ticket_data.update({
            "company_id": company_id,
            "platform": platform,
            "saved_at": datetime.utcnow().isoformat(),
            "storage_type": "file"
        })

        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(orjson.dumps(ticket_data, option=orjson.OPT_INDENT_2))

        return str(file_path)

    async def get_ticket(self, company_id: str, platform: str, ticket_id: str) -> Optional[Dict]:
        """티켓 데이터 조회"""
        file_path = self._get_company_path(company_id, platform) / "tickets" / f"{ticket_id}.json"

        if not file_path.exists():
            return None

        try:
            async with aiofiles.open(file_path, 'rb') as f:
                data = await f.read()
                return orjson.loads(data)
        except Exception as e:
            logger.error(f"Error reading ticket {ticket_id}: {e}")
            return None

    async def list_tickets(
        self,
        company_id: str,
        platform: str = None,
        status: str = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """티켓 목록 조회 (필터링 지원)"""
        tickets = []

        if platform:
            platforms = [platform]
        else:
            # 모든 플랫폼에서 검색
            company_path = self.base_path / company_id
            if not company_path.exists():
                return []
            platforms = [p.name for p in company_path.iterdir() if p.is_dir()]

        for plt in platforms:
            tickets_path = self._get_company_path(company_id, plt) / "tickets"
            if not tickets_path.exists():
                continue

            # 병렬로 파일 읽기
            tasks = []
            for file_path in tickets_path.glob("*.json"):
                tasks.append(self._read_ticket_file(file_path, status))

            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for result in results:
                    if isinstance(result, dict):
                        tickets.append(result)

        # 생성 시간 기준 정렬
        tickets.sort(key=lambda x: x.get("created_at", ""), reverse=True)

        # 페이지네이션
        return tickets[offset:offset + limit]

    async def _read_ticket_file(self, file_path: Path, status_filter: str = None) -> Optional[Dict]:
        """단일 티켓 파일 읽기"""
        try:
            async with aiofiles.open(file_path, 'rb') as f:
                data = await f.read()
                ticket = orjson.loads(data)

                # 상태 필터링
                if status_filter and ticket.get("status") != status_filter:
                    return None

                return ticket
        except Exception as e:
            logger.error(f"Error reading ticket file {file_path}: {e}")
            return None

    async def update_processing_status(
        self,
        company_id: str,
        platform: str,
        ticket_id: str,
        status: str
    ) -> bool:
        """처리 상태 업데이트"""
        try:
            ticket = await self.get_ticket(company_id, platform, ticket_id)
            if not ticket:
                return False

            ticket["processing_status"] = status
            ticket["status_updated_at"] = datetime.utcnow().isoformat()

            await self.save_ticket(company_id, platform, ticket)
            return True
        except Exception as e:
            logger.error(f"Error updating status for ticket {ticket_id}: {e}")
            return False

    async def save_summary(
        self,
        company_id: str,
        platform: str,
        item_id: str,
        summary_data: Dict
    ) -> bool:
        """LLM 요약 결과 저장"""
        try:
            summaries_path = self._get_company_path(company_id, platform) / "summaries"
            summaries_path.mkdir(parents=True, exist_ok=True)

            summary_file = summaries_path / f"{item_id}.json"
            
            summary_record = {
                "company_id": company_id,
                "platform": platform,
                "item_id": item_id,
                "summary": summary_data,
                "created_at": datetime.utcnow().isoformat()
            }

            async with aiofiles.open(summary_file, 'wb') as f:
                await f.write(orjson.dumps(summary_record, option=orjson.OPT_INDENT_2))

            return True
        except Exception as e:
            logger.error(f"Error saving summary for {item_id}: {e}")
            return False

    async def get_processing_progress(
        self,
        company_id: str,
        platform: str
    ) -> Dict:
        """처리 진행 상황 조회"""
        progress_path = self._get_progress_path(company_id, platform)
        progress_file = progress_path / "progress.json"

        if not progress_file.exists():
            return {
                "total_tickets": 0,
                "processed_tickets": 0,
                "failed_tickets": 0,
                "progress_percentage": 0.0,
                "last_updated": None
            }

        try:
            async with aiofiles.open(progress_file, 'rb') as f:
                data = await f.read()
                return orjson.loads(data)
        except Exception as e:
            logger.error(f"Error reading progress for {company_id}/{platform}: {e}")
            return {}

    async def save_kb_article(
        self,
        company_id: str,
        platform: str,
        article_data: Dict
    ) -> str:
        """지식베이스 문서 저장"""
        company_path = self._get_company_path(company_id, platform)
        kb_path = company_path / "knowledge_base"
        kb_path.mkdir(parents=True, exist_ok=True)

        article_id = article_data.get("id") or article_data.get("article_id")
        file_path = kb_path / f"{article_id}.json"

        # 메타데이터 추가
        article_data.update({
            "company_id": company_id,
            "platform": platform,
            "saved_at": datetime.utcnow().isoformat()
        })

        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(orjson.dumps(article_data, option=orjson.OPT_INDENT_2))

        return str(file_path)

    async def list_companies(self) -> List[str]:
        """등록된 회사 목록 조회"""
        if not self.base_path.exists():
            return []

        companies = []
        for company_dir in self.base_path.iterdir():
            if company_dir.is_dir():
                companies.append(company_dir.name)

        return sorted(companies)

    async def get_platform_stats(self, company_id: str) -> Dict[str, int]:
        """플랫폼별 데이터 통계"""
        stats = {}
        company_path = self.base_path / company_id

        if not company_path.exists():
            return stats

        for platform_dir in company_path.iterdir():
            if not platform_dir.is_dir():
                continue

            platform = platform_dir.name
            tickets_path = platform_dir / "tickets"
            kb_path = platform_dir / "knowledge_base"

            ticket_count = len(list(tickets_path.glob("*.json"))) if tickets_path.exists() else 0
            kb_count = len(list(kb_path.glob("*.json"))) if kb_path.exists() else 0

            stats[platform] = {
                "tickets": ticket_count,
                "knowledge_base": kb_count,
                "total": ticket_count + kb_count
            }

        return stats
```

---

## 🗃️ **PostgreSQL 기반 스토리지 (프로덕션)**

### 🗄️ **PostgreSQL 스키마 설계**

```sql
-- 멀티플랫폼/멀티테넌트 티켓 테이블
CREATE TABLE tickets (
    id SERIAL PRIMARY KEY,
    company_id VARCHAR(100) NOT NULL,
    platform VARCHAR(50) NOT NULL,
    ticket_id VARCHAR(100) NOT NULL,
    raw_data JSONB NOT NULL,
    processed_data JSONB,
    summary JSONB,
    processing_status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(company_id, platform, ticket_id)
);

-- 지식베이스 테이블
CREATE TABLE knowledge_base (
    id SERIAL PRIMARY KEY,
    company_id VARCHAR(100) NOT NULL,
    platform VARCHAR(50) NOT NULL,
    article_id VARCHAR(100) NOT NULL,
    title TEXT,
    content TEXT,
    raw_data JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(company_id, platform, article_id)
);

-- 처리 진행 상황 테이블
CREATE TABLE processing_progress (
    id SERIAL PRIMARY KEY,
    company_id VARCHAR(100) NOT NULL,
    platform VARCHAR(50) NOT NULL,
    total_items INTEGER DEFAULT 0,
    processed_items INTEGER DEFAULT 0,
    failed_items INTEGER DEFAULT 0,
    progress_percentage DECIMAL(5,2) DEFAULT 0.0,
    last_updated TIMESTAMP DEFAULT NOW(),
    UNIQUE(company_id, platform)
);

-- 인덱스 생성 (성능 최적화)
CREATE INDEX idx_tickets_company_platform ON tickets(company_id, platform);
CREATE INDEX idx_tickets_status ON tickets(processing_status);
CREATE INDEX idx_tickets_created_at ON tickets(created_at DESC);
CREATE INDEX idx_kb_company_platform ON knowledge_base(company_id, platform);

-- Row-level Security 활성화
ALTER TABLE tickets ENABLE ROW LEVEL SECURITY;
ALTER TABLE knowledge_base ENABLE ROW LEVEL SECURITY;
ALTER TABLE processing_progress ENABLE ROW LEVEL SECURITY;

-- 테넌트 격리 정책
CREATE POLICY tickets_company_isolation ON tickets
    FOR ALL TO app_user USING (company_id = current_setting('app.current_company_id'));

CREATE POLICY kb_company_isolation ON knowledge_base
    FOR ALL TO app_user USING (company_id = current_setting('app.current_company_id'));

CREATE POLICY progress_company_isolation ON processing_progress
    FOR ALL TO app_user USING (company_id = current_setting('app.current_company_id'));
```

### 🔗 **PostgresStorage 구현**

```python
import asyncpg
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text
import orjson

class PostgresStorage(StorageInterface):
    """PostgreSQL 기반 스토리지 (프로덕션용)"""

    def __init__(self, connection_string: str):
        self.engine = create_async_engine(
            connection_string,
            echo=False,
            pool_size=20,
            max_overflow=30
        )

    async def _set_tenant_context(self, session: AsyncSession, company_id: str):
        """Row-level Security를 위한 테넌트 컨텍스트 설정"""
        await session.execute(
            text("SET app.current_company_id = :company_id"),
            {"company_id": company_id}
        )

    async def save_ticket(self, company_id: str, platform: str, ticket_data: Dict) -> str:
        """PostgreSQL 데이터베이스에 티켓 저장"""
        async with AsyncSession(self.engine) as session:
            await self._set_tenant_context(session, company_id)

            # 기본 메타데이터 추가
            ticket_data.update({
                "company_id": company_id,
                "platform": platform,
                "saved_at": datetime.utcnow().isoformat(),
                "storage_type": "postgresql"
            })

            # 티켓 데이터 삽입/업데이트
            stmt = text("""
                INSERT INTO tickets (company_id, platform, ticket_id, raw_data, processing_status, created_at)
                VALUES (:company_id, :platform, :ticket_id, :raw_data, :status, NOW())
                ON CONFLICT (company_id, platform, ticket_id)
                DO UPDATE SET raw_data = EXCLUDED.raw_data, updated_at = NOW()
                RETURNING id
            """)

            result = await session.execute(stmt, {
                "company_id": company_id,
                "platform": platform,
                "ticket_id": ticket_data.get("ticket_id"),
                "raw_data": orjson.dumps(ticket_data).decode(),
                "status": ticket_data.get("processing_status", "pending")
            })

            await session.commit()
            return str(result.scalar())

    async def get_ticket(self, company_id: str, platform: str, ticket_id: str) -> Optional[Dict]:
        """PostgreSQL에서 티켓 조회"""
        async with AsyncSession(self.engine) as session:
            await self._set_tenant_context(session, company_id)

            stmt = text("""
                SELECT raw_data, processed_data, processing_status, created_at, updated_at
                FROM tickets
                WHERE company_id = :company_id AND platform = :platform AND ticket_id = :ticket_id
            """)

            result = await session.execute(stmt, {
                "company_id": company_id,
                "platform": platform,
                "ticket_id": ticket_id
            })

            row = result.first()
            if not row:
                return None

            ticket_data = orjson.loads(row.raw_data)
            ticket_data.update({
                "processing_status": row.processing_status,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None
            })

            if row.processed_data:
                ticket_data["processed_data"] = orjson.loads(row.processed_data)

            return ticket_data

    async def list_tickets(
        self,
        company_id: str,
        platform: str = None,
        status: str = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict]:
        """PostgreSQL에서 티켓 목록 조회"""
        async with AsyncSession(self.engine) as session:
            await self._set_tenant_context(session, company_id)

            # 동적 쿼리 생성
            where_clauses = ["company_id = :company_id"]
            params = {"company_id": company_id, "limit": limit, "offset": offset}

            if platform:
                where_clauses.append("platform = :platform")
                params["platform"] = platform

            if status:
                where_clauses.append("processing_status = :status")
                params["status"] = status

            query = f"""
                SELECT ticket_id, platform, raw_data, processed_data, processing_status, created_at
                FROM tickets
                WHERE {' AND '.join(where_clauses)}
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
            """

            result = await session.execute(text(query), params)

            tickets = []
            for row in result:
                ticket_data = orjson.loads(row.raw_data)
                ticket_data.update({
                    "platform": row.platform,
                    "processing_status": row.processing_status,
                    "created_at": row.created_at.isoformat() if row.created_at else None
                })

                if row.processed_data:
                    ticket_data["processed_data"] = orjson.loads(row.processed_data)

                tickets.append(ticket_data)

            return tickets

    async def update_processing_status(
        self,
        company_id: str,
        platform: str,
        ticket_id: str,
        status: str
    ) -> bool:
        """처리 상태 업데이트"""
        async with AsyncSession(self.engine) as session:
            await self._set_tenant_context(session, company_id)

            stmt = text("""
                UPDATE tickets
                SET processing_status = :status, updated_at = NOW()
                WHERE company_id = :company_id AND platform = :platform AND ticket_id = :ticket_id
            """)

            result = await session.execute(stmt, {
                "company_id": company_id,
                "platform": platform,
                "ticket_id": ticket_id,
                "status": status
            })

            await session.commit()
            return result.rowcount > 0

    async def save_summary(
        self,
        company_id: str,
        platform: str,
        item_id: str,
        summary_data: Dict
    ) -> bool:
        """LLM 요약 결과 저장"""
        async with AsyncSession(self.engine) as session:
            await self._set_tenant_context(session, company_id)

            stmt = text("""
                UPDATE tickets
                SET summary = :summary, updated_at = NOW()
                WHERE company_id = :company_id AND platform = :platform AND ticket_id = :item_id
            """)

            result = await session.execute(stmt, {
                "company_id": company_id,
                "platform": platform,
                "item_id": item_id,
                "summary": orjson.dumps(summary_data).decode()
            })

            await session.commit()
            return result.rowcount > 0

    async def get_processing_progress(
        self,
        company_id: str,
        platform: str
    ) -> Dict:
        """처리 진행 상황 조회"""
        async with AsyncSession(self.engine) as session:
            await self._set_tenant_context(session, company_id)

            stmt = text("""
                SELECT total_items, processed_items, failed_items, progress_percentage, last_updated
                FROM processing_progress
                WHERE company_id = :company_id AND platform = :platform
            """)

            result = await session.execute(stmt, {
                "company_id": company_id,
                "platform": platform
            })

            row = result.first()
            if not row:
                return {
                    "total_tickets": 0,
                    "processed_tickets": 0,
                    "failed_tickets": 0,
                    "progress_percentage": 0.0,
                    "last_updated": None
                }

            return {
                "total_tickets": row.total_items,
                "processed_tickets": row.processed_items,
                "failed_tickets": row.failed_items,
                "progress_percentage": float(row.progress_percentage),
                "last_updated": row.last_updated.isoformat() if row.last_updated else None
            }

    async def list_companies(self) -> List[str]:
        """등록된 회사 목록 조회"""
        async with AsyncSession(self.engine) as session:
            stmt = text("SELECT DISTINCT company_id FROM tickets ORDER BY company_id")
            result = await session.execute(stmt)
            return [row[0] for row in result]

    async def get_platform_stats(self, company_id: str) -> Dict[str, int]:
        """플랫폼별 데이터 통계"""
        async with AsyncSession(self.engine) as session:
            await self._set_tenant_context(session, company_id)

            # 티켓 통계
            ticket_stmt = text("""
                SELECT platform, COUNT(*) as count
                FROM tickets
                WHERE company_id = :company_id
                GROUP BY platform
            """)

            # KB 통계
            kb_stmt = text("""
                SELECT platform, COUNT(*) as count
                FROM knowledge_base
                WHERE company_id = :company_id
                GROUP BY platform
            """)

            ticket_result = await session.execute(ticket_stmt, {"company_id": company_id})
            kb_result = await session.execute(kb_stmt, {"company_id": company_id})

            stats = {}
            
            # 티켓 카운트
            for row in ticket_result:
                platform = row.platform
                if platform not in stats:
                    stats[platform] = {"tickets": 0, "knowledge_base": 0}
                stats[platform]["tickets"] = row.count

            # KB 카운트
            for row in kb_result:
                platform = row.platform
                if platform not in stats:
                    stats[platform] = {"tickets": 0, "knowledge_base": 0}
                stats[platform]["knowledge_base"] = row.count

            # 총계 계산
            for platform in stats:
                stats[platform]["total"] = stats[platform]["tickets"] + stats[platform]["knowledge_base"]

            return stats
```

---

## 🏭 **스토리지 팩토리 패턴**

### 🔧 **StorageFactory 구현**

```python
import os
from typing import Union

class StorageFactory:
    """환경에 따른 스토리지 구현 선택"""

    @staticmethod
    def create_storage() -> StorageInterface:
        """환경변수에 따라 적절한 스토리지 구현 반환"""
        storage_type = os.getenv("STORAGE_TYPE", "file").lower()

        if storage_type == "postgresql":
            connection_string = os.getenv("DATABASE_URL")
            if not connection_string:
                raise ValueError("PostgreSQL storage requires DATABASE_URL environment variable")
            return PostgresStorage(connection_string)

        elif storage_type == "file":
            base_path = os.getenv("DATA_PATH", "backend/data")
            return FileStorage(base_path)

        elif storage_type == "hybrid":
            # 마이그레이션용 하이브리드 스토리지
            return HybridStorage()

        else:
            raise ValueError(f"Unsupported storage type: {storage_type}")

    @staticmethod
    def get_supported_types() -> List[str]:
        """지원되는 스토리지 타입 목록"""
        return ["file", "postgresql", "hybrid"]

# 전역 스토리지 인스턴스
_storage_instance = None

def get_storage() -> StorageInterface:
    """싱글톤 스토리지 인스턴스 반환"""
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = StorageFactory.create_storage()
    return _storage_instance

# 사용 예시
async def example_usage():
    storage = get_storage()
    
    # 환경에 관계없이 동일한 API 사용
    await storage.save_ticket("wedosoft", "freshdesk", ticket_data)
    tickets = await storage.list_tickets("wedosoft", "freshdesk", status="resolved")
    progress = await storage.get_processing_progress("wedosoft", "freshdesk")
```

---

## 🔄 **하이브리드 스토리지 (마이그레이션용)**

### 🌉 **HybridStorage 구현**

```python
class HybridStorage(StorageInterface):
    """파일 → PostgreSQL 마이그레이션용 하이브리드 스토리지"""

    def __init__(self):
        self.file_storage = FileStorage()
        self.postgres_storage = PostgresStorage(os.getenv("DATABASE_URL"))
        self.use_postgres = os.getenv("HYBRID_USE_POSTGRES", "false").lower() == "true"

    async def save_ticket(self, company_id: str, platform: str, ticket_data: Dict) -> str:
        """두 스토리지에 모두 저장 (검증용)"""
        # 파일 저장 (백업)
        file_result = await self.file_storage.save_ticket(company_id, platform, ticket_data)
        
        # PostgreSQL 저장 (메인)
        try:
            postgres_result = await self.postgres_storage.save_ticket(company_id, platform, ticket_data)
            return postgres_result
        except Exception as e:
            logger.error(f"PostgreSQL save failed, using file storage: {e}")
            return file_result

    async def get_ticket(self, company_id: str, platform: str, ticket_id: str) -> Optional[Dict]:
        """PostgreSQL 우선, 실패 시 파일에서 조회"""
        if self.use_postgres:
            try:
                result = await self.postgres_storage.get_ticket(company_id, platform, ticket_id)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"PostgreSQL get failed, falling back to file: {e}")

        return await self.file_storage.get_ticket(company_id, platform, ticket_id)

    async def migrate_data(self, company_id: str, platform: str = None):
        """파일 데이터를 PostgreSQL로 마이그레이션"""
        logger.info(f"Starting migration for {company_id}/{platform or 'all'}")
        
        companies = [company_id] if company_id else await self.file_storage.list_companies()
        
        for company in companies:
            stats = await self.file_storage.get_platform_stats(company)
            
            for plt, platform_stats in stats.items():
                if platform and plt != platform:
                    continue
                
                logger.info(f"Migrating {platform_stats['tickets']} tickets for {company}/{plt}")
                
                # 티켓 마이그레이션
                tickets = await self.file_storage.list_tickets(company, plt, limit=10000)
                for ticket in tickets:
                    try:
                        await self.postgres_storage.save_ticket(company, plt, ticket)
                    except Exception as e:
                        logger.error(f"Failed to migrate ticket {ticket.get('ticket_id')}: {e}")

        logger.info("Migration completed")
```

---

## ⚠️ **스토리지 추상화 주의사항**

### 🚨 **구현 시 필수 준수사항**

1. **인터페이스 일관성**
   - 모든 구현체는 `StorageInterface` 완전 준수
   - 메서드 시그니처 변경 금지

2. **company_id 필수 태깅**
   - 모든 저장 메서드에 테넌트 식별자 포함
   - 데이터 격리 정책 일관성 유지

3. **에러 처리 표준화**
   - 구현체별 예외를 공통 예외로 변환
   - 로깅 레벨 및 형식 통일

4. **성능 최적화**
   - 대용량 데이터는 배치 처리 적용
   - 불필요한 추상화 오버헤드 최소화

5. **마이그레이션 안전성**
   - 파일 → DB 전환 시 데이터 손실 방지
   - 백업 및 롤백 전략 필수

---

## 📚 **관련 지침서**

- **[데이터 수집 패턴](data-collection-patterns.instructions.md)**: 수집된 데이터의 저장 처리
- **[멀티테넌트 보안](multitenant-security.instructions.md)**: 스토리지 레벨 데이터 격리
- **[시스템 아키텍처](system-architecture.instructions.md)**: 전체 스토리지 아키텍처 설계
- **[Quick Reference](quick-reference.instructions.md)**: 핵심 스토리지 패턴 요약

**이 스토리지 추상화 지침서는 개발부터 프로덕션까지 일관된 데이터 저장 전략을 제공합니다.**
