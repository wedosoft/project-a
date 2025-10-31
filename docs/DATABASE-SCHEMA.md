# AI Contact Center OS - Database Schema Documentation

**Generated**: 2025-10-31
**Namespace**: mvp-database-schema
**Migration**: backend/migrations/001_initial_schema.sql

## Database Configuration

### Connection Details
- **Host**: aws-1-ap-northeast-2.pooler.supabase.com
- **Port**: 6543
- **Database**: postgres
- **User**: postgres.zshtpaalelzyenprkuhw
- **Project ID**: zshtpaalelzyenprkuhw
- **API URL**: https://zshtpaalelzyenprkuhw.supabase.co

### Environment Variables
```env
SUPABASE_URL=https://zshtpaalelzyenprkuhw.supabase.co
SUPABASE_KEY=<anon_key>
SUPABASE_SERVICE_ROLE_KEY=<service_role_key>
SUPABASE_DB_HOST=aws-1-ap-northeast-2.pooler.supabase.com
SUPABASE_DB_PORT=6543
SUPABASE_DB_NAME=postgres
SUPABASE_DB_USER=postgres.zshtpaalelzyenprkuhw
SUPABASE_DB_PASSWORD=<password>
```

## Schema Overview

### Tables Created
1. **issue_blocks** - 티켓 지식 (증상/원인/해결책)
2. **kb_blocks** - 정책/절차 문서
3. **approval_logs** - AI 제안 및 승인 이력

### Applied Features
- ✅ **Row Level Security (RLS)** - tenant_id 기반 데이터 격리
- ✅ **Indexes** - 성능 최적화를 위한 인덱스
- ✅ **Sample Data** - 개발/테스트용 샘플 데이터
- ✅ **Comments** - 테이블 및 컬럼 설명

## Table Schemas

### 1. issue_blocks

**Purpose**: 티켓에서 추출한 증상, 원인, 해결책 정보 저장

**Columns**:
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | 고유 식별자 |
| tenant_id | TEXT | NOT NULL | 테넌트 ID (멀티테넌시) |
| ticket_id | TEXT | NOT NULL | 티켓 ID (Freshdesk) |
| block_type | TEXT | CHECK (symptom/cause/resolution) | 블록 유형 |
| product | TEXT | | 제품명 |
| component | TEXT | | 컴포넌트명 |
| error_code | TEXT | | 에러 코드 |
| content | TEXT | NOT NULL | 추출된 핵심 문장 (512~1024자) |
| meta | JSONB | | 추가 메타데이터 (언어, 태그 등) |
| embedding_id | TEXT | UNIQUE | Qdrant 벡터 ID 참조 |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 생성 시간 |

**Indexes**:
- `idx_issue_blocks_tenant_id` - tenant_id
- `idx_issue_blocks_ticket_id` - ticket_id
- `idx_issue_blocks_block_type` - block_type
- `idx_issue_blocks_product` - product
- `idx_issue_blocks_component` - component
- `idx_issue_blocks_error_code` - error_code
- `idx_issue_blocks_created_at` - created_at DESC

**RLS Policy**:
```sql
CREATE POLICY "Tenant isolation for issue_blocks" ON issue_blocks
    USING (tenant_id = current_setting('app.current_tenant_id', TRUE));
```

**Sample Data**: 6 records (demo-tenant)
- TICKET-001: 로그인 에러 (증상/원인/해결책)
- TICKET-002: API 타임아웃 (증상/원인/해결책)

### 2. kb_blocks

**Purpose**: 표준 절차 및 정책 문서 블록 저장

**Columns**:
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | 고유 식별자 |
| tenant_id | TEXT | NOT NULL | 테넌트 ID |
| article_id | TEXT | | KB 문서 ID |
| intent | TEXT | | 의도/목적 설명 |
| step | TEXT | | 절차 단계 |
| constraint_text | TEXT | | 제약사항 및 주의점 |
| example | TEXT | | 예시 |
| meta | JSONB | | 추가 메타데이터 |
| embedding_id | TEXT | UNIQUE | Qdrant 벡터 ID 참조 |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 생성 시간 |

**Indexes**:
- `idx_kb_blocks_tenant_id` - tenant_id
- `idx_kb_blocks_article_id` - article_id
- `idx_kb_blocks_created_at` - created_at DESC

**RLS Policy**:
```sql
CREATE POLICY "Tenant isolation for kb_blocks" ON kb_blocks
    USING (tenant_id = current_setting('app.current_tenant_id', TRUE));
```

**Sample Data**: 3 records (demo-tenant)
- KB-AUTH-001: 로그인 문제 해결
- KB-AUTH-002: 비밀번호 재설정
- KB-PERF-001: API 성능 최적화

### 3. approval_logs

**Purpose**: AI 제안 및 상담원 승인 이력 저장

**Columns**:
| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | 고유 식별자 |
| tenant_id | TEXT | NOT NULL | 테넌트 ID |
| ticket_id | TEXT | NOT NULL | 티켓 ID |
| draft_response | TEXT | | AI가 제안한 초안 |
| final_response | TEXT | | 상담원이 최종 승인/수정한 응답 |
| field_updates | JSONB | | 티켓 필드 업데이트 내역 |
| approval_status | TEXT | CHECK (approved/modified/rejected) | 승인 상태 |
| agent_id | TEXT | | 상담원 ID |
| feedback_notes | TEXT | | 피드백 메모 |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 생성 시간 |

**Indexes**:
- `idx_approval_logs_tenant_id` - tenant_id
- `idx_approval_logs_ticket_id` - ticket_id
- `idx_approval_logs_status` - approval_status
- `idx_approval_logs_created_at` - created_at DESC

**RLS Policy**:
```sql
CREATE POLICY "Tenant isolation for approval_logs" ON approval_logs
    USING (tenant_id = current_setting('app.current_tenant_id', TRUE));
```

**Sample Data**: 2 records (demo-tenant)
- TICKET-001: JWT 토큰 만료 시간 연장 (승인)
- TICKET-002: 데이터베이스 쿼리 최적화 (수정됨)

## Multi-Tenancy Architecture

### RLS (Row Level Security)

모든 테이블에 tenant_id 기반 RLS 정책이 적용되어 있습니다.

**정책 작동 방식**:
1. 애플리케이션이 데이터베이스 연결 시 tenant_id 설정
   ```sql
   SET app.current_tenant_id = 'tenant-xyz';
   ```
2. 이후 모든 쿼리는 자동으로 해당 tenant의 데이터만 접근
3. 다른 tenant의 데이터는 완전히 격리됨

**사용 예시**:
```python
# Python (psycopg2)
conn.cursor().execute("SET app.current_tenant_id = %s", (tenant_id,))

# 이후 쿼리는 자동으로 필터링됨
cursor.execute("SELECT * FROM issue_blocks")  # 해당 tenant 데이터만 반환
```

## Vector Integration (Qdrant)

### Embedding ID 관계

각 블록은 `embedding_id` 컬럼을 통해 Qdrant 벡터 데이터베이스의 벡터와 연결됩니다.

**Qdrant Collections**:
- `issue_embeddings` - issue_blocks의 멀티벡터 (symptom_vec, cause_vec, resolution_vec)
- `kb_embeddings` - kb_blocks의 멀티벡터 (intent_vec, procedure_vec)

**Workflow**:
1. PostgreSQL에 블록 데이터 저장
2. 임베딩 생성 (bge-m3 또는 e5-mistral)
3. Qdrant에 벡터 업서트
4. PostgreSQL의 embedding_id 업데이트

## Usage Examples

### 1. Insert New Issue Block

```sql
-- Set tenant context
SET app.current_tenant_id = 'my-tenant';

-- Insert issue block
INSERT INTO issue_blocks (
    tenant_id, ticket_id, block_type, product, component, content, meta
)
VALUES (
    'my-tenant',
    'TICKET-123',
    'symptom',
    'Product X',
    'Authentication',
    '사용자가 로그인할 수 없음',
    '{"lang": "ko", "tags": ["auth"]}'::jsonb
);
```

### 2. Query Similar Cases

```sql
-- Set tenant context
SET app.current_tenant_id = 'my-tenant';

-- Find similar symptoms
SELECT
    ticket_id,
    block_type,
    content,
    product,
    component
FROM issue_blocks
WHERE
    block_type = 'symptom'
    AND product = 'Product X'
ORDER BY created_at DESC
LIMIT 10;
```

### 3. Log Approval

```sql
-- Set tenant context
SET app.current_tenant_id = 'my-tenant';

-- Insert approval log
INSERT INTO approval_logs (
    tenant_id, ticket_id,
    draft_response, final_response,
    field_updates, approval_status, agent_id
)
VALUES (
    'my-tenant',
    'TICKET-123',
    'AI가 제안한 응답...',
    '상담원이 수정한 응답...',
    '{"category": "Technical", "priority": "High"}'::jsonb,
    'modified',
    'agent-001'
);
```

## Migration Management

### Initial Setup

```bash
# Run migration script
python3 scripts/init_supabase_schema.py
```

### Manual SQL Execution

SQL 파일을 Supabase Dashboard의 SQL Editor에서 직접 실행할 수도 있습니다:

1. Supabase Dashboard → SQL Editor
2. [backend/migrations/001_initial_schema.sql](../backend/migrations/001_initial_schema.sql) 내용 복사
3. 실행

### Verification Queries

```sql
-- Verify tables created
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
AND table_name IN ('issue_blocks', 'kb_blocks', 'approval_logs');

-- Verify RLS policies
SELECT tablename, policyname
FROM pg_policies
WHERE tablename IN ('issue_blocks', 'kb_blocks', 'approval_logs');

-- Count records
SELECT
    (SELECT COUNT(*) FROM issue_blocks) as issue_blocks_count,
    (SELECT COUNT(*) FROM kb_blocks) as kb_blocks_count,
    (SELECT COUNT(*) FROM approval_logs) as approval_logs_count;
```

## Performance Considerations

### Indexing Strategy

모든 주요 쿼리 패턴에 대해 인덱스가 생성되어 있습니다:

1. **Tenant Isolation**: tenant_id 인덱스 (모든 테이블)
2. **Time Series**: created_at DESC 인덱스 (최신 데이터 우선)
3. **Filtering**: product, component, error_code 인덱스
4. **Status Tracking**: approval_status 인덱스

### Query Optimization Tips

1. 항상 tenant_id 필터를 명시적으로 추가 (RLS가 자동으로 처리하지만 인덱스 힌트)
2. created_at 범위 쿼리 시 DESC 인덱스 활용
3. JSONB 컬럼(meta, field_updates) 쿼리 시 GIN 인덱스 고려 (향후 추가 가능)

## Security

### RLS Policies

- ✅ 모든 테이블에 RLS 활성화
- ✅ tenant_id 기반 완전한 데이터 격리
- ✅ 애플리케이션 레벨에서 tenant_id 설정 필수

### Access Control

- **ANON Key**: 읽기 전용 (RLS 적용)
- **SERVICE_ROLE Key**: 모든 권한 (RLS 우회 가능) - 백엔드 전용
- **Database Password**: PostgreSQL 직접 연결 (관리자 전용)

## Maintenance

### Backup Strategy

Supabase는 자동 백업을 제공합니다:
- 매일 자동 백업
- Point-in-time recovery (PITR)
- 수동 백업: Dashboard → Database → Backups

### Monitoring

주요 모니터링 지표:
- 테이블별 레코드 수
- 쿼리 성능 (느린 쿼리)
- RLS 정책 적용 상태
- 인덱스 사용률

---

**Created**: 2025-10-31
**Status**: ✅ Production Ready
**Migration File**: [backend/migrations/001_initial_schema.sql](../backend/migrations/001_initial_schema.sql)
**Verification**: All tables created, RLS applied, sample data inserted
