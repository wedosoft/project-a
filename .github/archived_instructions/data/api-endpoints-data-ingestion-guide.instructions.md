---
applyTo: "**"
---

# 🔄 데이터 수집 API 엔드포인트 가이드

_AI 참조 최적화 버전 - 실전 시행착오 기반 API 사용법_

## 🎯 **TL;DR - API 엔드포인트 핵심 요약**

### 🚨 **가장 중요한 교훈**
**`/ingest`와 `/ingest/jobs`는 완전히 다른 용도입니다!**
- `/ingest` → **즉시 실행** (동기식, 실시간 데이터 수집)
- `/ingest/jobs` → **작업 생성** (비동기식, 백그라운드 실행)

**🔑 핵심 파라미터 전달 규칙:**
- **인증 정보**: HTTP 헤더로만 전달 (X-Company-ID, X-API-Key 등)
- **수집 옵션**: POST body(JSON)로만 전달 (max_tickets, include_kb 등)
- **GET 쿼리 파라미터는 지원하지 않음**

**⚠️ 자주 발생하는 오류:**
- `max_tickets`를 null로 전달 시 NoneType 비교 오류 → 명시적 숫자 지정 필요
- 헤더 대신 POST body에 API 키 포함 → 인증 실패
- GET 쿼리로 파라미터 전달 → 파라미터 무시됨

### ⚡ **즉시 참조용 엔드포인트 맵**

| 엔드포인트 | 메소드 | 용도 | 실행 방식 | 사용 시점 |
|------------|--------|------|-----------|-----------|
| `/ingest` | POST | **데이터 즉시 수집** | 동기식 | 테스트, 소량 데이터 |
| `/ingest/jobs` | POST | **수집 작업 생성** | 비동기식 | 대량 데이터, 스케줄링 |
| `/ingest/jobs` | GET | **작업 목록 조회** | - | 진행 상황 확인 |
| `/ingest/jobs/{job_id}` | GET | **작업 상태 확인** | - | 특정 작업 모니터링 |
| `/ingest/jobs/{job_id}/control` | POST | **작업 제어** | - | 중지/재개/취소 |
| `/ingest/metrics` | GET | **수집 메트릭** | - | 성능 모니터링 |
| `/ingest/sync-summaries` | POST | **벡터DB 동기화** | - | 수집 후 검색 준비 |

---

## 🚀 **실전 사용법 - 시행착오 기반**

### 💡 **상황별 올바른 엔드포인트 선택**

#### 🔥 **즉시 데이터 확인이 필요한 경우**
```bash
# ✅ 올바른 방법: /ingest 사용 (헤더 + POST body)
curl -X POST "http://localhost:8000/ingest" \
  -H "X-Company-ID: wedosoft" \
  -H "X-Platform: freshdesk" \
  -H "X-Domain: wedosoft.freshdesk.com" \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "incremental": true,
    "include_kb": true,
    "max_tickets": 100,
    "max_articles": 50,
    "process_attachments": false
  }'

# 응답: 즉시 수집 실행되고 결과 반환
{
  "status": "completed",
  "results": {
    "tickets_collected": 87,
    "kb_articles_collected": 23,
    "attachments_processed": 0
  },
  "storage": {
    "database_path": "sqlite_dbs/wedosoft.db",
    "total_records": 110
  },
  "execution_time": "32.5s"
}
```

#### ⚠️ **잘못된 사용 사례**
```bash
# ❌ 틀린 방법 1: GET 쿼리 파라미터 사용
curl "http://localhost:8000/ingest?max_tickets=100&company_id=wedosoft"
# 결과: 파라미터가 무시됨 (POST body에만 적용됨)

# ❌ 틀린 방법 2: 헤더 없이 POST body에 인증 정보 포함
curl -X POST "http://localhost:8000/ingest" \
  -H "Content-Type: application/json" \
  -d '{
    "company_id": "wedosoft",
    "api_key": "your_api_key",
    "max_tickets": 100
  }'
# 결과: 인증 정보는 헤더에서만 인식됨
```

#### 🔄 **대량 데이터나 정기 수집이 필요한 경우**
```bash
# ✅ 올바른 방법: /ingest/jobs 사용 (헤더 + POST body)
curl -X POST "http://localhost:8000/ingest/jobs" \
  -H "X-Company-ID: wedosoft" \
  -H "X-Platform: freshdesk" \
  -H "X-Domain: wedosoft.freshdesk.com" \
  -H "X-API-Key: your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "incremental": false,
    "include_kb": true,
    "process_attachments": true,
    "batch_size": 100,
    "parallel_workers": 4,
    "auto_start": true
  }'

# 응답: 작업 ID 반환, 백그라운드에서 실행
{
  "job_id": "ingest-job-20250622-001",
  "status": "queued",
  "estimated_duration": "15-30 minutes",
  "progress_url": "/ingest/jobs/ingest-job-20250622-001"
}
```

---

## 📊 **엔드포인트별 상세 명세**

### 1️⃣ **POST /ingest - 즉시 데이터 수집**

**⚡ 언제 사용하나?**
- 설정 테스트 시
- 소량 데이터 수집 시 (< 1000건)
- 실시간 확인이 필요한 경우
- 디버깅 및 개발 시

**� 중요: 파라미터 전달 방식**
- **API 키, 도메인, 회사 ID**: HTTP 헤더로 전달 (보안상 필수)
- **수집 옵션**: POST body(JSON)로 전달
- **GET 쿼리 파라미터는 지원하지 않음**

**📥 HTTP 헤더 (필수)**
```bash
X-Company-ID: wedosoft
X-Platform: freshdesk
X-Domain: wedosoft.freshdesk.com
X-API-Key: your_freshdesk_api_key
Content-Type: application/json
```

**🔧 POST Body 예시 (JSON)**
```json
{
  "incremental": true,
  "purge": false,
  "process_attachments": true,
  "force_rebuild": false,
  "include_kb": true,
  "max_tickets": 500,
  "max_articles": 100
}
```

**💡 핵심 파라미터 설명**
- `max_tickets`: 수집할 최대 티켓 수 (null=무제한, 테스트용 100 권장)
- `max_articles`: 수집할 최대 KB 문서 수 (null=무제한, 테스트용 50 권장)
- `incremental`: 증분 업데이트 모드 (true=새로운 것만, false=전체)
- `include_kb`: 지식베이스 데이터 포함 여부 (true/false)
- `process_attachments`: 첨부파일 처리 여부 (true/false)
- `force_rebuild`: 데이터베이스 강제 재구축 (true/false)

**📤 응답 예시**
```json
{
  "status": "completed",
  "execution_id": "exec-20250622-143052",
  "results": {
    "tickets_collected": 245,
    "conversations_collected": 489,
    "kb_articles_collected": 35,
    "attachments_processed": 12
  },
  "storage": {
    "database_path": "sqlite_dbs/wedosoft.db",
    "tables_created": ["tickets", "conversations", "integrated_objects", "kb_articles"],
    "total_records": 781
  },
  "timing": {
    "started_at": "2025-06-22T14:30:52Z",
    "completed_at": "2025-06-22T14:31:37Z",
    "duration_seconds": 45.2
  },
  "next_steps": [
    "Use /ingest/sync-summaries to enable vector search",
    "Check data quality with /ingest/metrics"
  ]
}
```

### 2️⃣ **POST /ingest/jobs - 수집 작업 생성**

**⚡ 언제 사용하나?**
- 대량 데이터 수집 시 (> 1000건)
- 정기적 스케줄링이 필요한 경우
- 백그라운드 실행이 필요한 경우
- 여러 플랫폼 동시 수집 시

**� 중요: 파라미터 전달 방식**
- **API 키, 도메인, 회사 ID**: HTTP 헤더로 전달 (보안상 필수)
- **작업 옵션**: POST body(JSON)로 전달
- **GET 쿼리 파라미터는 지원하지 않음**

**📥 HTTP 헤더 (필수)**
```bash
X-Company-ID: wedosoft
X-Platform: freshdesk
X-Domain: wedosoft.freshdesk.com
X-API-Key: your_freshdesk_api_key
Content-Type: application/json
```

**🔧 POST Body 예시 (JSON)**
```json
{
  "incremental": true,
  "purge": false,
  "process_attachments": true,
  "force_rebuild": false,
  "include_kb": true,
  "batch_size": 50,
  "max_retries": 3,
  "parallel_workers": 2,
  "auto_start": true
}
```

**💡 핵심 파라미터 설명**
- `batch_size`: 배치 크기 (1-200, 기본값: 50)
- `max_retries`: 최대 재시도 횟수 (0-10, 기본값: 3)
- `parallel_workers`: 병렬 작업자 수 (1-8, 기본값: 4)
- `auto_start`: 생성 후 자동 시작 여부 (true/false, 기본값: true)
- `incremental`: 증분 업데이트 모드 (true=새로운 것만, false=전체)
- `include_kb`: 지식베이스 데이터 포함 여부 (true/false)

**📤 응답 예시**
```json
{
  "job_id": "ingest-job-wedosoft-20250622-001",
  "status": "queued",
  "priority": "normal",
  "estimated_duration": "15-30 minutes",
  "estimated_items": 2500,
  "created_at": "2025-06-22T14:35:00Z",
  "progress_tracking": {
    "status_url": "/ingest/jobs/ingest-job-wedosoft-20250622-001",
    "websocket_url": "ws://localhost:8000/ingest/jobs/ingest-job-wedosoft-20250622-001/stream"
  },
  "control": {
    "pause_url": "/ingest/jobs/ingest-job-wedosoft-20250622-001/control",
    "cancel_url": "/ingest/jobs/ingest-job-wedosoft-20250622-001/control"
  }
}
```

### 3️⃣ **GET /ingest/jobs - 작업 목록 조회**

**⚡ 언제 사용하나?**
- 전체 수집 작업 현황 파악
- 대시보드나 모니터링
- 문제 작업 식별

**🔧 쿼리 파라미터**
```bash
GET /ingest/jobs?company_id=wedosoft&status=running&limit=10&page=1
```

**📤 응답 예시**
```json
{
  "jobs": [
    {
      "job_id": "ingest-job-wedosoft-20250622-001",
      "company_id": "wedosoft",
      "platform": "freshdesk",
      "status": "running",
      "progress": {
        "current_step": "collecting_tickets",
        "completed_items": 150,
        "total_items": 500,
        "percentage": 30.0
      },
      "created_at": "2025-06-22T14:35:00Z",
      "started_at": "2025-06-22T14:35:15Z",
      "estimated_completion": "2025-06-22T14:50:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 10,
    "total": 15,
    "total_pages": 2
  },
  "summary": {
    "total_jobs": 15,
    "running": 2,
    "completed": 10,
    "failed": 2,
    "queued": 1
  }
}
```

### 4️⃣ **GET /ingest/jobs/{job_id} - 작업 상태 확인**

**⚡ 언제 사용하나?**
- 특정 작업의 상세 진행 상황 확인
- 오류 발생 시 디버깅
- 성능 분석

**📤 응답 예시**
```json
{
  "job_id": "ingest-job-wedosoft-20250622-001",
  "status": "running",
  "progress": {
    "current_step": "collecting_conversations",
    "step_details": "Processing page 5 of 12",
    "completed_items": 445,
    "total_items": 1200,
    "percentage": 37.1,
    "items_per_second": 8.5
  },
  "timing": {
    "created_at": "2025-06-22T14:35:00Z",
    "started_at": "2025-06-22T14:35:15Z",
    "last_activity": "2025-06-22T14:42:30Z",
    "estimated_completion": "2025-06-22T14:48:45Z",
    "elapsed_seconds": 435
  },
  "statistics": {
    "tickets_collected": 150,
    "conversations_collected": 295,
    "kb_articles_collected": 0,
    "errors_encountered": 2,
    "retries_performed": 1
  },
  "logs": [
    {
      "timestamp": "2025-06-22T14:42:25Z",
      "level": "INFO",
      "message": "Successfully processed ticket batch 5/12",
      "details": {"batch_size": 50, "processing_time": 5.2}
    },
    {
      "timestamp": "2025-06-22T14:42:30Z",
      "level": "WARN",
      "message": "Rate limit approaching, adding delay",
      "details": {"remaining_requests": 150, "reset_time": "2025-06-22T14:43:00Z"}
    }
  ]
}
```

### 5️⃣ **POST /ingest/jobs/{job_id}/control - 작업 제어**

**⚡ 언제 사용하나?**
- 실행 중인 작업을 일시 중지/재개
- 문제 발생 시 작업 취소
- 리소스 관리를 위한 우선순위 조정

**🔧 요청 예시**
```json
{
  "action": "pause",  // "pause", "resume", "cancel", "priority_change"
  "reason": "System maintenance required",
  "options": {
    "graceful_shutdown": true,
    "save_progress": true
  }
}
```

**📤 응답 예시**
```json
{
  "job_id": "ingest-job-wedosoft-20250622-001",
  "action_performed": "pause",
  "previous_status": "running",
  "current_status": "paused",
  "timestamp": "2025-06-22T14:45:00Z",
  "progress_saved": true,
  "resume_capability": true,
  "message": "Job paused successfully. Progress saved at 445/1200 items."
}
```

### 6️⃣ **GET /ingest/metrics - 수집 메트릭**

**⚡ 언제 사용하나?**
- 성능 모니터링 및 최적화
- 시스템 리소스 사용량 확인
- SLA 준수 여부 확인

**📤 응답 예시**
```json
{
  "system_metrics": {
    "active_jobs": 2,
    "queued_jobs": 1,
    "total_jobs_today": 15,
    "success_rate": 93.3,
    "average_job_duration": "12.5 minutes"
  },
  "performance_metrics": {
    "items_per_second": 8.7,
    "api_response_time_avg": 245,
    "database_write_time_avg": 12,
    "memory_usage_mb": 256,
    "cpu_usage_percent": 15.2
  },
  "platform_metrics": {
    "freshdesk": {
      "rate_limit_usage": 65.0,
      "api_errors_today": 3,
      "successful_requests": 1247,
      "average_response_time": 180
    }
  },
  "data_quality": {
    "duplicate_rate": 2.1,
    "validation_error_rate": 0.5,
    "missing_fields_rate": 1.2
  }
}
```

### 7️⃣ **POST /ingest/sync-summaries - 벡터DB 동기화**

**⚡ 언제 사용하나?**
- 데이터 수집 완료 후 검색 활성화
- 벡터 임베딩 업데이트
- 검색 성능 최적화

**🔧 요청 예시**
```json
{
  "company_id": "wedosoft",
  "sync_options": {
    "force_rebuild": false,
    "incremental_only": true,
    "embedding_model": "text-embedding-3-small"
  }
}
```

---

## 🚨 **실전 문제 해결 가이드**

### ❌ **자주 발생하는 실수들**

#### 1. **파라미터 전달 방식 혼동**
```bash
# ❌ 문제: GET 쿼리 파라미터로 전달
curl "http://localhost:8000/ingest?max_tickets=100&company_id=wedosoft"
# 결과: 파라미터가 무시됨

# ❌ 문제: POST body에 인증 정보 포함
curl -X POST "http://localhost:8000/ingest" \
  -d '{"company_id": "wedosoft", "api_key": "key", "max_tickets": 100}'
# 결과: 인증 실패

# ✅ 해결: 헤더 + POST body 분리
curl -X POST "http://localhost:8000/ingest" \
  -H "X-Company-ID: wedosoft" \
  -H "X-API-Key: your_key" \
  -H "Content-Type: application/json" \
  -d '{"max_tickets": 100, "include_kb": true}'
```

#### 2. **엔드포인트 혼동**
```bash
# ❌ 문제: 즉시 확인하려고 /ingest/jobs 사용
# 결과: 작업만 생성되고 기다려야 함

# ✅ 해결: 즉시 확인은 /ingest 사용
curl -X POST "http://localhost:8000/ingest" # 즉시 실행
```

#### 3. **max_tickets/max_articles NoneType 오류**
```bash
# ❌ 문제: max_tickets를 null로 전달했을 때 비교 오류 발생
# 원인: None과 int 비교 시 TypeError

# ✅ 해결: 명시적으로 값 지정 또는 생략
{
  "max_tickets": 100,  # 구체적 숫자 지정
  "max_articles": 50   # 또는 필드 자체를 생략
}
```

#### 4. **응답 형식 오해**
```bash
# ❌ 문제: /ingest/jobs 응답에서 즉시 결과 기대
{
  "job_id": "abc-123",
  "status": "queued"  # 아직 시작도 안됨!
}

# ✅ 해결: 상태 확인 엔드포인트로 모니터링
curl "http://localhost:8000/ingest/jobs/abc-123"
```

### 🔧 **디버깅 체크리스트**

#### **데이터 수집이 안 될 때**
1. ✅ **헤더 확인**: X-Company-ID, X-Platform, X-API-Key가 올바른가?
2. ✅ **도메인 확인**: X-Domain이 올바른 형식인가? (예: company.freshdesk.com)
3. ✅ **파라미터 위치**: max_tickets, max_articles는 POST body에 있나?
4. ✅ **Content-Type**: application/json으로 설정했나?
5. ✅ **API 키 권한**: 플랫폼에서 API 키가 활성화되어 있나?
6. ✅ **Rate Limit**: API 호출 제한에 걸리지 않았나?
7. ✅ **엔드포인트**: 올바른 엔드포인트를 사용했나? (`/ingest` vs `/ingest/jobs`)
8. ✅ **로그 확인**: 서버 로그에 오류가 있나?

#### **max_tickets/max_articles 관련 오류**
```bash
# ❌ 문제: TypeError: '>' not supported between instances of 'NoneType' and 'int'
# 원인: max_tickets가 None일 때 비교 연산 오류

# ✅ 해결 방법:
# 1. 명시적으로 숫자 지정
{"max_tickets": 100, "max_articles": 50}

# 2. 필드 자체를 생략 (null 대신)
{"include_kb": true, "incremental": true}

# 3. 0으로 지정 (수집 안함)
{"max_tickets": 0, "max_articles": 0}
```

#### **성능이 느릴 때**
1. ✅ batch_size를 조정했나? (기본값: 50, 권장: 100-200)
2. ✅ parallel_workers를 늘렸나? (기본값: 4, 최대: 8)
3. ✅ API Rate Limit을 확인했나?
4. ✅ 동시 작업이 너무 많지 않나?
5. ✅ 메트릭을 확인했나? (`GET /ingest/metrics`)
6. ✅ incremental 모드를 사용했나? (전체 수집은 느림)

---

## 🎯 **베스트 프랙티스**

### 🚀 **개발/테스트 단계**
```bash
# 1. 연결 및 인증 테스트 (소량 데이터)
curl -X POST "http://localhost:8000/ingest" \
  -H "X-Company-ID: test-company" \
  -H "X-Platform: freshdesk" \
  -H "X-Domain: test.freshdesk.com" \
  -H "X-API-Key: your_test_key" \
  -H "Content-Type: application/json" \
  -d '{"max_tickets": 10, "max_articles": 5, "include_kb": true}'

# 2. 서버 상태 확인
curl "http://localhost:8000/health"

# 3. 전체 수집 작업 생성 (백그라운드)
curl -X POST "http://localhost:8000/ingest/jobs" \
  -H "X-Company-ID: test-company" \
  -H "X-Platform: freshdesk" \
  -H "X-Domain: test.freshdesk.com" \
  -H "X-API-Key: your_test_key" \
  -H "Content-Type: application/json" \
  -d '{"incremental": true, "batch_size": 50, "auto_start": true}'

# 4. 진행 상황 모니터링
curl "http://localhost:8000/ingest/jobs/{job_id}"

# 5. 벡터 검색 활성화
curl -X POST "http://localhost:8000/ingest/sync-summaries" \
  -H "X-Company-ID: test-company" \
  -H "Content-Type: application/json" \
  -d '{"company_id": "test-company"}'
```

### 🔄 **운영 단계**
```bash
# 정기 수집 작업 설정 (예: 매일 새벽 2시)
curl -X POST "http://localhost:8000/ingest/jobs" \
  -H "X-Company-ID: production-company" \
  -H "X-Platform: freshdesk" \
  -H "X-Domain: company.freshdesk.com" \
  -H "X-API-Key: ${PROD_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "incremental": true,
    "include_kb": true,
    "batch_size": 100,
    "parallel_workers": 6,
    "auto_start": true
  }'

# 대시보드용 메트릭 수집 (매 5분)
curl "http://localhost:8000/ingest/metrics"

# 작업 상태 모니터링 (매 1분)
curl "http://localhost:8000/ingest/jobs?status=running"

# 실패한 작업 재시작
curl -X POST "http://localhost:8000/ingest/jobs/{job_id}/control" \
  -H "Content-Type: application/json" \
  -d '{"action": "resume"}'
```

### 📊 **모니터링 및 알림**
- **실패율 > 5%** → 알림 (API 키 확인, Rate Limit 확인)
- **Rate Limit 사용률 > 80%** → 경고 (batch_size 줄이기)
- **작업 대기 시간 > 30분** → 리소스 부족 확인
- **메모리 사용률 > 80%** → 스케일 업 고려
- **max_tickets/max_articles NoneType 오류** → 파라미터 명시적 지정

### 💡 **파라미터 최적화 가이드**
```json
// 🏃 빠른 테스트용 (< 1분)
{
  "max_tickets": 10,
  "max_articles": 5,
  "process_attachments": false,
  "incremental": true
}

// ⚖️ 균형적 수집용 (5-15분)
{
  "max_tickets": 500,
  "max_articles": 100,
  "process_attachments": true,
  "batch_size": 100,
  "parallel_workers": 4,
  "incremental": true
}

// 🚀 대량 수집용 (30분+)
{
  "incremental": false,
  "batch_size": 200,
  "parallel_workers": 8,
  "process_attachments": true,
  "include_kb": true
}
```

---

## 🔗 **관련 지침서 링크**

- 📊 [데이터 수집 패턴](./data-collection-patterns.instructions.md)
- 🏗️ [API 아키텍처](../development/api-architecture-file-structure.instructions.md)
- 🔒 [멀티테넌트 보안](../core/multitenant-security.instructions.md)
- ⚡ [성능 최적화](../core/performance-optimization.instructions.md)
- 🚨 [에러 처리](../development/error-handling-debugging.instructions.md)

---

**📝 마지막 업데이트**: 2025-06-22 (파라미터 전달 방식 명확화)
**🔧 주요 변경사항**: 
- HTTP 헤더 vs POST body 파라미터 구분 명시
- max_tickets/max_articles NoneType 오류 해결 방법 추가
- 실전 사용 예시 및 curl 명령어 업데이트
- 디버깅 체크리스트 확장

**🎯 다음 업데이트**: 웹소켓 스트리밍 엔드포인트 추가 예정
