# API 상세 문서

## 🌐 API 개요

**Base URL**: `http://localhost:8000` (개발) / `https://api.yourdomain.com` (프로덕션)  
**인증**: API Key 기반 (`X-API-Key` 헤더)  
**테넌트 격리**: `X-Tenant-Id` 헤더  
**응답 형식**: JSON  
**문자 인코딩**: UTF-8

## 📋 API 엔드포인트 상세

### 🎫 티켓 작업 API

#### 티켓 초기화
```http
GET /init/{ticket_id}
```
**설명**: 티켓 ID를 기반으로 전체 컨텍스트를 초기화하고 유사 티켓, 관련 문서를 반환

**매개변수**:
- `ticket_id` (path, required): Freshdesk 티켓 ID
- `tenant_id` (header, optional): 테넌트 식별자
- `include_similar` (query, optional, default=true): 유사 티켓 포함 여부
- `include_articles` (query, optional, default=true): KB 문서 포함 여부

**응답 예시**:
```json
{
  "ticket": {
    "id": "123",
    "subject": "결제 오류 문의",
    "description": "결제 진행 중 오류가 발생했습니다",
    "status": "open",
    "priority": "high"
  },
  "similar_tickets": [
    {
      "ticket_id": "456",
      "subject": "결제 실패 관련 문의",
      "similarity_score": 0.92,
      "resolution": "resolved"
    }
  ],
  "related_articles": [
    {
      "article_id": "789",
      "title": "결제 오류 해결 가이드",
      "relevance_score": 0.88,
      "category": "결제"
    }
  ],
  "context": {
    "total_similar": 5,
    "total_articles": 3,
    "processing_time": 1.2
  }
}
```

#### 티켓 요약
```http
GET /init/{ticket_id}/summary
```
**설명**: 특정 티켓의 AI 생성 요약 반환

**응답 예시**:
```json
{
  "ticket_id": "123",
  "summary": {
    "main_issue": "결제 프로세스 중 카드 인증 실패",
    "customer_sentiment": "frustrated",
    "urgency": "high",
    "key_points": [
      "여러 번 시도했으나 계속 실패",
      "다른 카드로도 동일한 문제 발생",
      "급한 주문 건"
    ]
  },
  "metadata": {
    "generated_at": "2025-01-09T10:30:00Z",
    "model_used": "gpt-4"
  }
}
```

#### 유사 티켓 검색
```http
GET /init/{ticket_id}/similar
```
**설명**: 벡터 유사도 기반 유사 티켓 검색

**매개변수**:
- `limit` (query, optional, default=10): 반환할 최대 티켓 수
- `threshold` (query, optional, default=0.7): 최소 유사도 점수

**응답 예시**:
```json
{
  "source_ticket": "123",
  "similar_tickets": [
    {
      "ticket_id": "456",
      "subject": "결제 오류 발생",
      "similarity_score": 0.95,
      "status": "resolved",
      "resolution": "카드사 일시적 오류로 확인",
      "created_at": "2025-01-08T09:00:00Z"
    }
  ],
  "search_metadata": {
    "total_found": 15,
    "returned": 10,
    "search_time_ms": 45
  }
}
```

### 🔍 검색 및 쿼리 API

#### 일반 쿼리
```http
POST /query
```
**설명**: 자연어 쿼리를 통한 지능형 검색

**요청 본문**:
```json
{
  "query": "환불 처리 방법",
  "search_type": "hybrid",
  "filters": {
    "category": "billing",
    "date_range": {
      "from": "2025-01-01",
      "to": "2025-01-09"
    }
  },
  "limit": 20
}
```

**응답 예시**:
```json
{
  "results": [
    {
      "type": "article",
      "id": "kb_001",
      "title": "환불 정책 및 처리 절차",
      "content": "환불은 구매일로부터 14일 이내...",
      "relevance_score": 0.94,
      "highlights": ["환불 처리", "14일 이내"]
    },
    {
      "type": "ticket",
      "id": "t_789",
      "subject": "환불 요청",
      "relevance_score": 0.87
    }
  ],
  "metadata": {
    "total_results": 45,
    "search_time_ms": 120,
    "search_method": "hybrid"
  }
}
```

#### 하이브리드 검색
```http
POST /hybrid-search
```
**설명**: 벡터 검색과 키워드 검색을 결합한 고급 검색

**요청 본문**:
```json
{
  "query": "로그인 오류 해결",
  "vector_weight": 0.7,
  "keyword_weight": 0.3,
  "search_config": {
    "use_synonyms": true,
    "expand_query": true,
    "language": "ko"
  }
}
```

### 💬 답변 생성 API

#### AI 답변 생성
```http
POST /reply
```
**설명**: 티켓 컨텍스트 기반 AI 답변 생성

**요청 본문**:
```json
{
  "ticket_id": "123",
  "context": {
    "include_similar": true,
    "include_kb": true,
    "customer_history": true
  },
  "reply_config": {
    "tone": "professional",
    "language": "ko",
    "max_length": 500,
    "include_references": true
  }
}
```

**응답 예시**:
```json
{
  "reply": {
    "content": "안녕하세요, 고객님. 결제 오류로 불편을 드려 죄송합니다...",
    "references": [
      {
        "type": "kb_article",
        "id": "kb_123",
        "title": "결제 오류 해결 가이드"
      }
    ],
    "suggested_actions": [
      "카드사 확인",
      "대체 결제 수단 안내"
    ]
  },
  "metadata": {
    "model": "gpt-4",
    "tokens_used": 450,
    "generation_time_ms": 2300
  }
}
```

### 📥 데이터 수집 API

#### 데이터 수집 작업 생성
```http
POST /ingest/jobs
```
**설명**: 새로운 데이터 수집 작업 생성

**요청 본문**:
```json
{
  "job_type": "full",
  "sources": ["tickets", "kb_articles"],
  "config": {
    "batch_size": 100,
    "parallel_workers": 4,
    "date_filter": {
      "from": "2024-01-01",
      "to": "2025-01-09"
    }
  }
}
```

**응답 예시**:
```json
{
  "job_id": "job_20250109_001",
  "status": "created",
  "estimated_items": 5000,
  "estimated_time_minutes": 30,
  "created_at": "2025-01-09T10:00:00Z"
}
```

#### 수집 작업 상태 확인
```http
GET /ingest/jobs/{job_id}
```
**설명**: 특정 수집 작업의 진행 상태 확인

**응답 예시**:
```json
{
  "job_id": "job_20250109_001",
  "status": "in_progress",
  "progress": {
    "total_items": 5000,
    "processed_items": 3500,
    "failed_items": 5,
    "percentage": 70
  },
  "current_phase": "embedding_generation",
  "elapsed_time_seconds": 900,
  "estimated_remaining_seconds": 450
}
```

#### 작업 제어
```http
POST /ingest/jobs/{job_id}/control
```
**설명**: 실행 중인 작업을 일시정지, 재개, 취소

**요청 본문**:
```json
{
  "action": "pause"  // "pause", "resume", "cancel"
}
```

### 👤 에이전트 관리 API

#### 에이전트 목록
```http
GET /agents
```
**설명**: 모든 에이전트 목록과 상태 반환

**매개변수**:
- `status` (query, optional): active, inactive, all
- `has_license` (query, optional): true, false
- `page` (query, optional, default=1): 페이지 번호
- `limit` (query, optional, default=50): 페이지당 항목 수

**응답 예시**:
```json
{
  "agents": [
    {
      "agent_id": "agent_001",
      "name": "김철수",
      "email": "kim@company.com",
      "status": "active",
      "license_type": "pro",
      "last_login": "2025-01-09T09:00:00Z"
    }
  ],
  "pagination": {
    "current_page": 1,
    "total_pages": 5,
    "total_items": 245
  }
}
```

#### 라이선스 업데이트
```http
PUT /agents/{agent_id}/license
```
**설명**: 특정 에이전트의 라이선스 정보 업데이트

**요청 본문**:
```json
{
  "license_type": "pro",
  "valid_until": "2025-12-31",
  "features": ["advanced_search", "ai_reply", "bulk_operations"]
}
```

### 🎛️ 관리자 API

#### 시스템 상태
```http
GET /admin/status
```
**설명**: 전체 시스템 상태 및 통계 반환

**응답 예시**:
```json
{
  "system": {
    "status": "healthy",
    "uptime_seconds": 86400,
    "version": "2.1.0"
  },
  "database": {
    "vector_db": {
      "status": "connected",
      "collections": 5,
      "total_vectors": 150000
    },
    "postgresql": {
      "status": "connected",
      "size_mb": 2048
    }
  },
  "resources": {
    "cpu_usage_percent": 45,
    "memory_usage_mb": 1024,
    "disk_usage_gb": 50
  },
  "statistics": {
    "total_tickets": 50000,
    "total_articles": 1000,
    "daily_queries": 5000
  }
}
```

#### 데이터 삭제
```http
POST /admin/purge
```
**설명**: 지정된 데이터 삭제 (주의: 복구 불가능)

**요청 본문**:
```json
{
  "target": "tickets",
  "conditions": {
    "older_than_days": 365,
    "status": ["closed", "resolved"]
  },
  "dry_run": true
}
```

#### 스케줄러 관리
```http
POST /admin/scheduler/toggle
```
**설명**: 자동 수집 스케줄러 활성화/비활성화

**요청 본문**:
```json
{
  "enabled": true,
  "schedule": {
    "type": "cron",
    "expression": "0 2 * * *",
    "timezone": "Asia/Seoul"
  }
}
```

### 📊 성능 모니터링 API

#### 성능 대시보드
```http
GET /performance/dashboard
```
**설명**: 종합 성능 메트릭 대시보드

**응답 예시**:
```json
{
  "overview": {
    "avg_response_time_ms": 250,
    "requests_per_second": 100,
    "error_rate_percent": 0.5
  },
  "endpoints": [
    {
      "path": "/query",
      "avg_time_ms": 300,
      "p95_time_ms": 500,
      "request_count": 10000
    }
  ],
  "cache": {
    "hit_rate_percent": 85,
    "size_mb": 512,
    "evictions_per_hour": 100
  }
}
```

#### 캐시 통계
```http
GET /performance/cache/stats
```
**설명**: 캐시 성능 상세 통계

**응답 예시**:
```json
{
  "cache_stats": {
    "total_keys": 5000,
    "memory_usage_mb": 256,
    "hit_rate": 0.85,
    "miss_rate": 0.15,
    "eviction_count": 100
  },
  "by_category": {
    "embeddings": {
      "keys": 2000,
      "hit_rate": 0.95
    },
    "search_results": {
      "keys": 1500,
      "hit_rate": 0.80
    }
  }
}
```

### 📎 첨부파일 API

#### 첨부파일 다운로드 URL
```http
GET /attachments/{attachment_id}/download-url
```
**설명**: 첨부파일의 임시 다운로드 URL 생성

**응답 예시**:
```json
{
  "attachment_id": "att_123",
  "download_url": "https://cdn.example.com/attachments/att_123?token=xyz",
  "expires_at": "2025-01-09T11:00:00Z",
  "file_info": {
    "name": "invoice.pdf",
    "size_bytes": 524288,
    "mime_type": "application/pdf"
  }
}
```

#### 대량 URL 가져오기
```http
GET /attachments/bulk-urls
```
**설명**: 여러 첨부파일의 URL을 한 번에 가져오기

**매개변수**:
- `attachment_ids` (query, required): 콤마로 구분된 첨부파일 ID 목록

**응답 예시**:
```json
{
  "attachments": [
    {
      "attachment_id": "att_123",
      "download_url": "https://cdn.example.com/attachments/att_123",
      "status": "available"
    },
    {
      "attachment_id": "att_124",
      "status": "not_found"
    }
  ]
}
```

## 🔐 인증 및 보안

### API 키 인증
모든 API 요청에는 유효한 API 키가 필요합니다:

```http
X-API-Key: your-api-key-here
```

### 테넌트 격리
멀티테넌트 환경에서는 테넌트 ID 헤더가 필요합니다:

```http
X-Tenant-Id: tenant-123
```

### 속도 제한
- 기본 제한: 분당 100 요청
- 버스트 제한: 초당 10 요청
- 제한 초과 시 `429 Too Many Requests` 응답

### CORS 설정
```javascript
// 허용된 오리진
[
  "https://yourcompany.freshdesk.com",
  "http://localhost:10001"
]
```

## 🚨 오류 처리

### 표준 오류 응답
```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "요청한 리소스를 찾을 수 없습니다",
    "details": {
      "resource_type": "ticket",
      "resource_id": "123"
    }
  },
  "request_id": "req_abc123",
  "timestamp": "2025-01-09T10:00:00Z"
}
```

### 오류 코드
| 코드 | HTTP 상태 | 설명 |
|------|-----------|------|
| `INVALID_REQUEST` | 400 | 잘못된 요청 형식 |
| `UNAUTHORIZED` | 401 | 인증 실패 |
| `FORBIDDEN` | 403 | 권한 없음 |
| `NOT_FOUND` | 404 | 리소스 없음 |
| `RATE_LIMITED` | 429 | 속도 제한 초과 |
| `INTERNAL_ERROR` | 500 | 서버 내부 오류 |
| `SERVICE_UNAVAILABLE` | 503 | 서비스 일시 중단 |

## 📈 성능 최적화 팁

### 페이지네이션 사용
대량의 데이터를 요청할 때는 항상 페이지네이션을 사용하세요:
```http
GET /agents?page=1&limit=50
```

### 필드 선택
필요한 필드만 요청하여 응답 크기를 줄이세요:
```http
GET /tickets?fields=id,subject,status
```

### 캐싱 활용
변경이 적은 데이터는 클라이언트 측에서 캐싱하세요:
```javascript
// Cache-Control 헤더 확인
Cache-Control: public, max-age=3600
```

### 배치 요청
여러 개의 개별 요청 대신 배치 엔드포인트를 사용하세요:
```http
POST /batch
{
  "requests": [
    {"method": "GET", "path": "/tickets/1"},
    {"method": "GET", "path": "/tickets/2"}
  ]
}
```

## 🔄 버전 관리

### API 버전
현재 API 버전: v2.1.0

### 버전 헤더
```http
X-API-Version: 2.1.0
```

### 지원 중단 정책
- 새 버전 출시 후 6개월간 이전 버전 지원
- 지원 중단 3개월 전 공지

## 📚 추가 리소스

- [Postman Collection](./postman/collection.json)
- [OpenAPI Specification](./openapi.yaml)
- [SDK 문서](./sdk/README.md)
- [웹훅 가이드](./webhooks/GUIDE.md)

---

*최종 업데이트: 2025년 1월 9일*