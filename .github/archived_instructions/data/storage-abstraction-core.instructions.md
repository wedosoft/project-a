---
applyTo: "**"
---

# 🗄️ 스토리지 추상화 핵심 지침서

_AI 참조 최적화 버전 - 멀티테넌트 데이터베이스 추상화 핵심 패턴_

## 🎯 **TL;DR - 스토리지 추상화 핵심 요약**

### 💡 **즉시 참조용 핵심 포인트**

**스토리지 전략**:
- **PostgreSQL**: 메인 데이터베이스 (구조화된 데이터)
- **Qdrant**: 벡터 저장소 (임베딩 데이터)
- **Redis**: 캐시 및 세션 저장소
- **S3/MinIO**: 파일 저장소 (첨부파일)

**멀티테넌트 격리**:
- **Database Level**: 각 테넌트별 스키마 분리
- **Application Level**: company_id 기반 필터링
- **Cache Level**: 테넌트별 캐시 키 네임스페이스

**데이터 모델링**:
```python
# 기본 테넌트 모델
class BaseModel(SQLAlchemyBaseModel):
    company_id: str = Field(..., index=True)
    platform: str = Field(..., index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

---

## 🏗️ **데이터베이스 추상화 레이어**

### 📊 **기본 데이터 모델**

```python
from sqlalchemy import Column, String, DateTime, Text, Integer, Boolean, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid

Base = declarative_base()

class BaseModel(Base):
    __abstract__ = True
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(String(50), nullable=False, index=True)
    platform = Column(String(20), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_tenant_composite', 'company_id', 'platform'),
    )

class Ticket(BaseModel):
    __tablename__ = 'tickets'
    
    # 기본 필드
    ticket_id = Column(String(50), nullable=False)  # 플랫폼별 ID
    title = Column(String(500), nullable=False)
    description = Column(Text)
    status = Column(String(50), nullable=False, index=True)
    priority = Column(String(20), nullable=False, index=True)
    
    # 고객 정보
    requester_email = Column(String(255), index=True)
    requester_name = Column(String(100))
    
    # 처리 정보
    assignee_email = Column(String(255), index=True)
    assignee_name = Column(String(100))
    
    # 메타데이터
    tags = Column(JSONB)  # 태그 배열
    custom_fields = Column(JSONB)  # 플랫폼별 커스텀 필드
    
    # LLM 처리 결과
    summary = Column(JSONB)  # 구조화된 요약
    is_processed = Column(Boolean, default=False, index=True)
    
    __table_args__ = (
        Index('idx_ticket_composite', 'company_id', 'platform', 'ticket_id'),
        Index('idx_ticket_status', 'company_id', 'platform', 'status'),
        Index('idx_ticket_priority', 'company_id', 'platform', 'priority'),
        Index('idx_ticket_assignee', 'company_id', 'platform', 'assignee_email'),
        Index('idx_ticket_processed', 'company_id', 'platform', 'is_processed'),
    )

class Conversation(BaseModel):
    __tablename__ = 'conversations'
    
    ticket_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    conversation_id = Column(String(50), nullable=False)  # 플랫폼별 대화 ID
    
    # 메시지 내용
    content = Column(Text, nullable=False)
    message_type = Column(String(20), nullable=False)  # 'public', 'private', 'note'
    
    # 작성자 정보
    author_email = Column(String(255), index=True)
    author_name = Column(String(100))
    author_type = Column(String(20))  # 'agent', 'customer', 'system'
    
    # 첨부파일 정보
    attachments = Column(JSONB)  # 첨부파일 메타데이터
    
    __table_args__ = (
        Index('idx_conversation_composite', 'company_id', 'platform', 'ticket_id'),
        Index('idx_conversation_type', 'company_id', 'platform', 'message_type'),
        Index('idx_conversation_author', 'company_id', 'platform', 'author_email'),
    )
```

### 🔄 **데이터 액세스 패턴**

```python
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from typing import List, Dict, Optional

class TicketRepository:
    def __init__(self, db: Session):
        self.db = db
    
    async def get_tickets(
        self,
        company_id: str,
        platform: str,
        filters: Dict = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Ticket]:
        """멀티테넌트 티켓 조회"""
        
        query = self.db.query(Ticket).filter(
            and_(
                Ticket.company_id == company_id,
                Ticket.platform == platform
            )
        )
        
        # 필터 적용
        if filters:
            if 'status' in filters:
                query = query.filter(Ticket.status.in_(filters['status']))
            
            if 'priority' in filters:
                query = query.filter(Ticket.priority.in_(filters['priority']))
            
            if 'assignee_email' in filters:
                query = query.filter(Ticket.assignee_email.in_(filters['assignee_email']))
            
            if 'is_processed' in filters:
                query = query.filter(Ticket.is_processed == filters['is_processed'])
            
            if 'date_range' in filters:
                start_date = filters['date_range']['start']
                end_date = filters['date_range']['end']
                query = query.filter(
                    and_(
                        Ticket.created_at >= start_date,
                        Ticket.created_at <= end_date
                    )
                )
        
        return query.offset(offset).limit(limit).all()
    
    async def get_ticket_by_id(
        self,
        company_id: str,
        platform: str,
        ticket_id: str
    ) -> Optional[Ticket]:
        """단일 티켓 조회 (보안 검증 포함)"""
        
        return self.db.query(Ticket).filter(
            and_(
                Ticket.company_id == company_id,
                Ticket.platform == platform,
                Ticket.ticket_id == ticket_id
            )
        ).first()
    
    async def create_ticket(
        self,
        company_id: str,
        platform: str,
        ticket_data: Dict
    ) -> Ticket:
        """새 티켓 생성"""
        
        ticket = Ticket(
            company_id=company_id,
            platform=platform,
            **ticket_data
        )
        
        self.db.add(ticket)
        self.db.flush()  # ID 생성을 위해 flush
        return ticket
    
    async def update_ticket(
        self,
        company_id: str,
        platform: str,
        ticket_id: str,
        update_data: Dict
    ) -> Optional[Ticket]:
        """티켓 업데이트"""
        
        ticket = await self.get_ticket_by_id(company_id, platform, ticket_id)
        if not ticket:
            return None
        
        for key, value in update_data.items():
            if hasattr(ticket, key):
                setattr(ticket, key, value)
        
        ticket.updated_at = datetime.utcnow()
        return ticket
    
    async def get_ticket_stats(
        self,
        company_id: str,
        platform: str
    ) -> Dict:
        """티켓 통계 조회"""
        
        base_query = self.db.query(Ticket).filter(
            and_(
                Ticket.company_id == company_id,
                Ticket.platform == platform
            )
        )
        
        # 상태별 통계
        status_stats = self.db.query(
            Ticket.status,
            func.count(Ticket.id).label('count')
        ).filter(
            and_(
                Ticket.company_id == company_id,
                Ticket.platform == platform
            )
        ).group_by(Ticket.status).all()
        
        # 우선순위별 통계
        priority_stats = self.db.query(
            Ticket.priority,
            func.count(Ticket.id).label('count')
        ).filter(
            and_(
                Ticket.company_id == company_id,
                Ticket.platform == platform
            )
        ).group_by(Ticket.priority).all()
        
        return {
            'total_tickets': base_query.count(),
            'status_distribution': {stat.status: stat.count for stat in status_stats},
            'priority_distribution': {stat.priority: stat.count for stat in priority_stats},
            'processed_count': base_query.filter(Ticket.is_processed == True).count(),
            'unprocessed_count': base_query.filter(Ticket.is_processed == False).count()
        }
```

---

## 🚀 **캐시 추상화 레이어**

### 📦 **Redis 캐시 패턴**

```python
import redis.asyncio as redis
import orjson
from typing import Any, Optional, Dict, List

class CacheManager:
    def __init__(self, redis_url: str):
        self.redis = redis.from_url(redis_url)
        self.default_ttl = 300  # 5분
    
    def _get_cache_key(self, company_id: str, platform: str, key: str) -> str:
        """테넌트별 캐시 키 생성"""
        return f"{company_id}:{platform}:{key}"
    
    async def get(
        self,
        company_id: str,
        platform: str,
        key: str
    ) -> Optional[Any]:
        """캐시 조회"""
        
        cache_key = self._get_cache_key(company_id, platform, key)
        
        try:
            cached_data = await self.redis.get(cache_key)
            if cached_data:
                return orjson.loads(cached_data)
            return None
        except Exception as e:
            logger.error(f"Cache get error: {e}")
            return None
    
    async def set(
        self,
        company_id: str,
        platform: str,
        key: str,
        value: Any,
        ttl: int = None
    ) -> bool:
        """캐시 저장"""
        
        cache_key = self._get_cache_key(company_id, platform, key)
        ttl = ttl or self.default_ttl
        
        try:
            serialized_data = orjson.dumps(value)
            await self.redis.setex(cache_key, ttl, serialized_data)
            return True
        except Exception as e:
            logger.error(f"Cache set error: {e}")
            return False
    
    async def delete(
        self,
        company_id: str,
        platform: str,
        key: str
    ) -> bool:
        """캐시 삭제"""
        
        cache_key = self._get_cache_key(company_id, platform, key)
        
        try:
            await self.redis.delete(cache_key)
            return True
        except Exception as e:
            logger.error(f"Cache delete error: {e}")
            return False
    
    async def delete_pattern(
        self,
        company_id: str,
        platform: str,
        pattern: str
    ) -> int:
        """패턴 매칭 캐시 삭제"""
        
        search_pattern = self._get_cache_key(company_id, platform, pattern)
        
        try:
            keys = await self.redis.keys(search_pattern)
            if keys:
                await self.redis.delete(*keys)
                return len(keys)
            return 0
        except Exception as e:
            logger.error(f"Cache delete pattern error: {e}")
            return 0

# 전역 캐시 매니저
cache_manager = CacheManager(os.getenv("REDIS_URL"))
```

---

## 📁 **파일 저장소 추상화**

### 🗂️ **S3/MinIO 파일 관리**

```python
import boto3
from botocore.exceptions import ClientError
import mimetypes
from typing import Optional, Dict, List

class FileStorageManager:
    def __init__(self, endpoint_url: str, access_key: str, secret_key: str, bucket_name: str):
        self.s3_client = boto3.client(
            's3',
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key
        )
        self.bucket_name = bucket_name
    
    def _get_file_key(self, company_id: str, platform: str, file_path: str) -> str:
        """테넌트별 파일 키 생성"""
        return f"{company_id}/{platform}/{file_path}"
    
    async def upload_file(
        self,
        company_id: str,
        platform: str,
        file_path: str,
        file_content: bytes,
        content_type: str = None
    ) -> Dict:
        """파일 업로드"""
        
        file_key = self._get_file_key(company_id, platform, file_path)
        
        if not content_type:
            content_type = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'
        
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=file_key,
                Body=file_content,
                ContentType=content_type
            )
            
            return {
                'success': True,
                'file_key': file_key,
                'file_path': file_path,
                'size': len(file_content),
                'content_type': content_type
            }
            
        except ClientError as e:
            return {
                'success': False,
                'error': str(e),
                'file_path': file_path
            }
    
    async def download_file(
        self,
        company_id: str,
        platform: str,
        file_path: str
    ) -> Optional[bytes]:
        """파일 다운로드"""
        
        file_key = self._get_file_key(company_id, platform, file_path)
        
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=file_key
            )
            
            return response['Body'].read()
            
        except ClientError as e:
            logger.error(f"File download error: {e}")
            return None
    
    async def delete_file(
        self,
        company_id: str,
        platform: str,
        file_path: str
    ) -> bool:
        """파일 삭제"""
        
        file_key = self._get_file_key(company_id, platform, file_path)
        
        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=file_key
            )
            return True
            
        except ClientError as e:
            logger.error(f"File delete error: {e}")
            return False
    
    async def list_files(
        self,
        company_id: str,
        platform: str,
        prefix: str = ""
    ) -> List[Dict]:
        """파일 목록 조회"""
        
        search_prefix = self._get_file_key(company_id, platform, prefix)
        
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=search_prefix
            )
            
            files = []
            for obj in response.get('Contents', []):
                files.append({
                    'key': obj['Key'],
                    'size': obj['Size'],
                    'last_modified': obj['LastModified'],
                    'etag': obj['ETag']
                })
            
            return files
            
        except ClientError as e:
            logger.error(f"File list error: {e}")
            return []

# 전역 파일 스토리지 매니저
file_storage = FileStorageManager(
    endpoint_url=os.getenv("S3_ENDPOINT_URL"),
    access_key=os.getenv("S3_ACCESS_KEY"),
    secret_key=os.getenv("S3_SECRET_KEY"),
    bucket_name=os.getenv("S3_BUCKET_NAME")
)
```

---

## ✅ **스토리지 최적화 체크리스트**

### 🗄️ **데이터베이스 최적화**

- [ ] **복합 인덱스** 설정 (company_id + platform + 기타)
- [ ] **쿼리 최적화** (N+1 문제 방지)
- [ ] **연결 풀링** 설정
- [ ] **읽기 전용 복제본** 활용

### 📦 **캐시 최적화**

- [ ] **테넌트별 네임스페이스** 분리
- [ ] **TTL 설정** (적절한 만료 시간)
- [ ] **캐시 무효화** 전략
- [ ] **메모리 사용량** 모니터링

### 📁 **파일 저장소 최적화**

- [ ] **테넌트별 경로** 분리
- [ ] **파일 타입** 검증
- [ ] **용량 제한** 설정
- [ ] **CDN 연동** (정적 파일)

---

## 🔗 **관련 지침서**

- **벡터 저장소**: `vector-storage-core.instructions.md`
- **데이터 워크플로우**: `data-workflow.instructions.md`
- **성능 최적화**: `performance-optimization.instructions.md`
- **보안 설정**: `multitenant-security.instructions.md`

> **참고**: 이 지침서는 스토리지 추상화의 핵심 패턴만 다룹니다. 상세 구현은 legacy 폴더의 원본 파일을 참조하세요.
