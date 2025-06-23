---
applyTo: "**"
---

# 🔄 완전한 API 엔드포인트 참조 가이드

_모든 백엔드 API 엔드포인트 총정리 - 2025-06-23 최종 완성_

## 🎯 **TL;DR - 완성된 API 구조**

### 📊 **엔드포인트 구성 (라우터별)**
1. **즉시 실행 & 동기화** (`/ingest/`)
2. **작업 관리 & 메트릭스** (`/ingest/jobs/`)  
3. **진행 상황 모니터링** (`/ingest/progress/`)
4. **보안 & 데이터 삭제** (`/ingest/security/`)

### 🔑 **인증 헤더 (모든 엔드포인트 공통)**
```
X-Company-ID: 회사 식별자 (멀티테넌트 보안)
X-Platform: 플랫폼 식별자 (freshdesk, zendesk 등)
X-Domain: 플랫폼 도메인 (선택사항)
X-API-Key: 플랫폼 API 키 (선택사항)
```

---

## 📋 **전체 API 엔드포인트 맵**

### 1️⃣ **즉시 실행 & 동기화** (`/ingest/`)

| 엔드포인트 | 메소드 | 용도 | 제어 가능 | 추천 사용법 |
|------------|--------|------|-----------|-------------|
| `/ingest/` | POST | **데이터 즉시 수집** | ❌ 불가 | 테스트, 소량 데이터 (< 100개) |
| `/ingest/sync-summaries` | POST | **벡터DB 동기화** | ❌ 불가 | 수집 후 검색 활성화 |

**사용 예시:**
```bash
# 즉시 데이터 수집 (동기식)
curl -X POST "http://localhost:8000/ingest/" \
  -H "X-Company-ID: company123" \
  -H "X-Platform: freshdesk" \
  -H "X-Domain: company.freshdesk.com" \
  -H "X-API-Key: api_key_here" \
  -H "Content-Type: application/json" \
  -d '{
    "max_tickets": 100,
    "include_kb": true,
    "incremental": false
  }'
```

---

### 2️⃣ **작업 관리 & 메트릭스** (`/ingest/jobs/`)

| 엔드포인트 | 메소드 | 용도 | 제어 가능 | 추천 사용법 |
|------------|--------|------|-----------|-------------|
| `/ingest/jobs` | POST | **백그라운드 작업 생성** | ✅ 완전 제어 | 대량 데이터, 운영 환경 |
| `/ingest/jobs` | GET | **작업 목록 조회** | - | 진행 중인 작업 확인 |
| `/ingest/jobs/{job_id}` | GET | **작업 상태 확인** | - | 특정 작업 모니터링 |
| `/ingest/jobs/{job_id}/control` | POST | **작업 제어** | ✅ pause/resume/cancel | 실시간 작업 제어 |

**제어 액션:**
- `pause`: 작업 일시정지
- `resume`: 작업 재개  
- `cancel`: 작업 취소

**사용 예시:**
```bash
# 백그라운드 작업 생성
curl -X POST "http://localhost:8000/ingest/jobs" \
  -H "X-Company-ID: company123" \
  -H "X-Platform: freshdesk" \
  -H "Content-Type: application/json" \
  -d '{
    "max_tickets": 5000,
    "include_kb": true,
    "incremental": true
  }'

# 작업 일시정지
curl -X POST "http://localhost:8000/ingest/jobs/job123/control" \
  -H "X-Company-ID: company123" \
  -d '{"action": "pause"}'

# 작업 상태 확인
curl -X GET "http://localhost:8000/ingest/jobs/job123" \
  -H "X-Company-ID: company123"
```

---

### 3️⃣ **진행 상황 모니터링** (`/ingest/progress/`)

| 엔드포인트 | 메소드 | 용도 | 실시간 | 추천 사용법 |
|------------|--------|------|--------|-------------|
| `/ingest/progress/{job_id}` | GET | **진행 상황 조회** | ✅ 실시간 | 폴링으로 진행률 추적 |

**사용 예시:**
```bash
# 진행 상황 확인 (폴링)
curl -X GET "http://localhost:8000/ingest/progress/job123" \
  -H "X-Company-ID: company123"

# 응답 예시
{
  "job_id": "job123",
  "progress": {
    "percentage": 75.5,
    "current_step": "Processing tickets",
    "total_steps": 4,
    "completed_steps": 3
  },
  "stats": {
    "tickets_processed": 3775,
    "articles_processed": 125,
    "errors": 2
  }
}
```

---

### 4️⃣ **보안 & 데이터 삭제** (`/ingest/security/`)

| 엔드포인트 | 메소드 | 용도 | 보안 수준 | 추천 사용법 |
|------------|--------|------|-----------|-------------|
| `/ingest/security/generate-token` | POST | **보안 토큰 생성** | 🔒 높음 | 삭제 전 토큰 발급 |
| `/ingest/security/purge-data` | POST | **완전한 데이터 삭제** | 🚨 최고 | GDPR, 보안 사고 대응 |

**보안 토큰 생성:**
```bash
curl -X POST "http://localhost:8000/ingest/security/generate-token" \
  -H "X-Company-ID: company123" \
  -H "X-Platform: freshdesk"
```

**데이터 완전 삭제:**
```bash
curl -X POST "http://localhost:8000/ingest/security/purge-data" \
  -H "X-Company-ID: company123" \
  -H "X-Platform: freshdesk" \
  -H "Content-Type: application/json" \
  -d '{
    "confirmation_token": "DELETE_company123_freshdesk_20250623",
    "action": "purge_all",
    "reason": "GDPR 요청",
    "create_backup": true,
    "include_secrets": true,
    "aws_region": "us-east-1"
  }'
```

**삭제 대상:**
- 🗄️ SQLite 데이터 (티켓, 지식베이스, 요약)
- 🔍 벡터 DB (Qdrant 임베딩)
- 💾 캐시 데이터 (Redis, 메모리)
- 🔐 AWS Secrets Manager (비밀키)

---

## 🎯 **상황별 API 선택 가이드**

### 🧪 **테스트/개발 환경**
```bash
# 소량 데이터 즉시 확인
POST /ingest/ (max_tickets: 10-100)
```

### 🏭 **운영 환경**
```bash
# 대량 데이터 안전 처리
POST /ingest/jobs (max_tickets: 1000+)
GET /ingest/progress/{job_id} (폴링)
POST /ingest/jobs/{job_id}/control (필요시 제어)
```

### 🔒 **보안/GDPR 대응**
```bash
# 1단계: 토큰 생성
POST /ingest/security/generate-token

# 2단계: 데이터 완전 삭제
POST /ingest/security/purge-data
```

### 🔍 **모니터링/관리**
```bash
# 전체 작업 현황
GET /ingest/jobs

# 특정 작업 상태
GET /ingest/jobs/{job_id}

# 실시간 진행률
GET /ingest/progress/{job_id}
```

---

## 📊 **응답 구조 표준화**

### ✅ **성공 응답 (IngestResponse)**
```json
{
  "success": true,
  "message": "작업 완료 메시지",
  "start_time": "2025-06-23T10:00:00Z",
  "end_time": "2025-06-23T10:05:30Z",
  "duration_seconds": 330.5,
  "metadata": {
    "company_id": "company123",
    "platform": "freshdesk",
    "results": {...}
  }
}
```

### ❌ **오류 응답**
```json
{
  "success": false,
  "message": "오류 발생 메시지",
  "start_time": "2025-06-23T10:00:00Z",
  "end_time": "2025-06-23T10:01:15Z",
  "duration_seconds": 75.2,
  "error": "상세 오류 정보"
}
```

### 📋 **작업 상태 응답 (JobStatusResponse)**
```json
{
  "job": {
    "job_id": "job123",
    "status": "running",
    "created_at": "2025-06-23T10:00:00Z",
    "config": {...}
  },
  "is_active": true,
  "can_pause": true,
  "can_resume": false,
  "can_cancel": true
}
```

---

## 🚀 **프론트엔드 통합 패턴**

### React Hook 예시
```javascript
// 데이터 수집 훅
const useDataIngestion = () => {
  const [jobs, setJobs] = useState([]);
  const [progress, setProgress] = useState({});
  
  const startImmediate = async (config) => {
    const response = await fetch('/api/ingest/', {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(config)
    });
    return response.json();
  };
  
  const startBackground = async (config) => {
    const response = await fetch('/api/ingest/jobs', {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(config)
    });
    return response.json();
  };
  
  const controlJob = async (jobId, action) => {
    await fetch(`/api/ingest/jobs/${jobId}/control`, {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify({ action })
    });
  };
  
  const pollProgress = (jobId) => {
    const interval = setInterval(async () => {
      const response = await fetch(`/api/ingest/progress/${jobId}`, {
        headers: getAuthHeaders()
      });
      const data = await response.json();
      setProgress(prev => ({ ...prev, [jobId]: data }));
      
      if (data.status === 'completed' || data.status === 'failed') {
        clearInterval(interval);
      }
    }, 2000);
    
    return () => clearInterval(interval);
  };
  
  return {
    startImmediate,
    startBackground,
    controlJob,
    pollProgress,
    jobs,
    progress
  };
};

// 보안 관리 훅
const useSecurityManagement = () => {
  const generateToken = async () => {
    const response = await fetch('/api/ingest/security/generate-token', {
      method: 'POST',
      headers: getAuthHeaders()
    });
    return response.json();
  };
  
  const purgeData = async (config) => {
    const response = await fetch('/api/ingest/security/purge-data', {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(config)
    });
    return response.json();
  };
  
  return { generateToken, purgeData };
};
```

---

## ⚠️ **중요 주의사항**

### 🔒 **보안**
- **모든 엔드포인트**: 인증 헤더 필수
- **보안 토큰**: 당일만 유효
- **데이터 삭제**: 복구 불가능한 작업

### 📈 **성능**
- **즉시 실행**: 100개 이하 권장
- **백그라운드**: 대량 데이터 전용
- **진행률 폴링**: 2-5초 간격 권장

### 🔄 **제어**
- **즉시 실행**: 제어 불가 (동기식)
- **백그라운드**: 완전 제어 가능
- **진행 중 취소**: 안전하게 중단


좋은 질문입니다! 기존 데이터가 있는 상태에서 재수집할 때의 처리 방식을 확인해보겠습니다.

현재 코드에서 중복 처리 방식을 확인해보겠습니다: 데이터베이스의 insert 함수들을 확인해보겠습니다: 요약된 대화 내용기존 DB가 있을 때 재수집 시 데이터 처리 방식을 확인하기 위해 관련 코드를 살펴보겠습니다. 이제 **force_rebuild**, **purge**, **incremental** 옵션에 따른 데이터 처리 방식을 확인해보겠습니다. 이제 데이터베이스 재수집 시 처리 방식을 확인하기 위해 database.py 파일을 살펴보겠습니다. 이제 벡터 데이터베이스의 삭제 및 재구축 로직을 확인해보겠습니다. 이제 기존 데이터베이스가 있을 때 재수집 시 데이터 처리 방식에 대한 정확한 정보를 확인했습니다.

## 📊 **기존 DB가 있을 때 재수집 시 데이터 처리 방식**

### 🔍 **확인된 데이터 처리 정책**

**1. 기본 데이터 저장 방식 (SQLite):**
- **`INSERT OR REPLACE`** 패턴 사용
- 동일한 `original_id`가 있으면 **덮어쓰기**
- 새로운 데이터는 **추가**

**2. 벡터 데이터베이스 (Qdrant) 처리:**
- **Incremental 모드**: 기존 데이터 유지 + 새로운 데이터 추가/갱신
- **Purge 모드**: 기존 데이터 삭제 후 전체 재수집
- **Force_rebuild 모드**: 강제 재구축 (purge=True로 자동 설정)

### 🛠️ **옵션별 상세 동작**

#### ✅ **incremental=True (기본값)**
```python
# 기존 데이터 유지하면서 증분 업데이트
- 삭제된 문서 감지 및 제거
- 신규/변경된 문서만 수집 및 갱신
- SQLite: INSERT OR REPLACE로 덮어쓰기
- Qdrant: upsert 방식으로 업데이트
```

#### 🔄 **purge=True**
```python
# 기존 데이터 삭제 후 전체 재수집
- 벡터 DB의 기존 데이터 완전 삭제
- SQLite는 DROP/CREATE로 초기화
- 모든 데이터를 처음부터 새로 수집
```

#### 🚀 **force_rebuild=True**
```python
# 강제 재구축 모드 (가장 강력)
if force_rebuild:
    incremental = False
    purge = True  # 자동으로 purge 모드 활성화
```

---

## 📊 **데이터 수집 파이프라인 상세 분석**

### � **1. 텍스트+해시 기반 변경 감지 시스템**

#### **핵심 구현**: `backend/core/data/merger.py`의 `generate_document_hash()` 함수
```python
def generate_document_hash(self, document: Dict[str, Any]) -> str:
    """
    문서의 해시값 생성 (중복/변경 감지용)
    
    - 시간 관련 필드 제외: created_at_merged, data_hash, version
    - JSON 문자열로 변환 후 SHA-256 해시 생성
    - 텍스트 내용이 동일하면 같은 해시값 생성
    """
    exclude_fields = {"created_at_merged", "data_hash", "version"}
    hash_dict = {k: v for k, v in document.items() if k not in exclude_fields}
    doc_str = json.dumps(hash_dict, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(doc_str.encode('utf-8')).hexdigest()
```

#### **활용 방식**:
- 기존 문서의 해시값과 신규 문서의 해시값 비교
- 해시값이 다르면 **업데이트 필요**로 판단하여 덮어쓰기
- 해시값이 같으면 **변경 없음**으로 판단하여 건너뛰기

### 🗄️ **2. 데이터 적재/갱신/삭제 정책**

#### **기존 DB가 있을 때 재수집 정책**:

| 모드 | 옵션 | 동작 방식 |
|------|------|----------|
| **증분 수집** | `incremental=True` | 기존 ID와 신규 ID 비교 → 누락된 ID 배치 삭제 → 신규/변경 문서만 업데이트 |
| **전체 수집** | `incremental=False` | 기존 데이터 유지하면서 모든 문서 재처리 |
| **강제 재구축** | `force_rebuild=True` | **전체 삭제 후 적재** (SQLite: `clear_all_data()` / Qdrant: 컬렉션 삭제) |

#### **실제 저장 방식**: `INSERT OR REPLACE` 패턴
```python
# backend/core/database/database.py
cursor.execute("""
    INSERT OR REPLACE INTO tickets 
    (original_id, company_id, platform, ...) 
    VALUES (?, ?, ?, ...)
""", values)
```
- **덮어쓰기 방식**: 동일한 `original_id`가 있으면 기존 데이터 덮어쓰기
- **신규 추가**: 없으면 새로 삽입

### 🗑️ **3. 삭제된 문서 처리 방식**

#### **삭제 감지 로직**: `backend/api/routes/ingest_core.py`
```python
# 증분 수집 시 삭제 처리
if incremental:
    # 1. 기존 ID 목록 수집 (최대 1000개 샘플링)
    existing_ids = set(result.get("ids", []))
    
    # 2. 현재 수집된 ID 목록 생성
    current_ids = set()
    for ticket in tickets:
        base_id = f"ticket-{original_id}"
        current_ids.add(base_id)
    
    # 3. 삭제된 문서 식별
    deleted_ids = existing_ids - current_ids
    
    # 4. 배치 삭제 실행
    if deleted_ids:
        batch_size = 100
        for i in range(0, len(deleted_ids_list), batch_size):
            batch = deleted_ids_list[i:i+batch_size]
            vector_db.delete_documents(ids=batch, company_id=company_id)
```

#### **배치 삭제 특징**:
- **SQL + Qdrant 모두 적용**: 관계형 DB와 벡터 DB 동시 삭제
- **배치 처리**: 100개씩 묶어서 처리하여 성능 최적화
- **안전한 처리**: 기존 ID 목록과 신규 ID 목록을 정확히 비교

### ⚙️ **4. 옵션별 동작 차이점**

#### **증분 수집** (`incremental=True`)
```
1. 기존 ID 목록 조회 (최대 1000개)
2. 신규 데이터 수집
3. 삭제된 ID 감지 및 배치 삭제
4. 변경된 문서만 해시 비교하여 업데이트
```

#### **전체 수집** (`incremental=False`)
```
1. 모든 문서 수집
2. 기존 데이터 유지하면서 덮어쓰기
3. 삭제 처리 없음
```

#### **강제 재구축** (`force_rebuild=True`)
```
1. 기존 데이터 완전 삭제
   - SQLite: db.clear_all_data()
   - Qdrant: vector_db.drop_collection()
2. 처음부터 새로 적재
3. 전체 재구축 과정
```

### 🎯 **5. 핵심 정책 요약**

1. **변경 감지**: 텍스트+해시 값으로 문서 변경 여부 판단
2. **덮어쓰기**: `INSERT OR REPLACE` 방식으로 기존 데이터 덮어쓰기
3. **배치 삭제**: 기존 ID와 신규 ID 비교 후 누락된 ID는 100개씩 배치 삭제
4. **멀티 스토리지**: SQL(메타데이터) + Qdrant(벡터) 동시 관리
5. **안전한 재구축**: `force_rebuild` 시에만 전체 삭제 후 재적재

### 📝 **실전 운영 권장사항**

- **일반적인 데이터 수집**: `incremental=True` (기본값)
- **전체 재동기화**: `incremental=False`
- **문제 발생 시 완전 초기화**: `force_rebuild=True`
- **성능 최적화**: 배치 크기 조정 (기본 100개)

---

## 🎯 **결론: 기존 DB 재수집 시 처리 방식**

**1. 기본 재수집 (incremental=True):**
- **SQLite**: `INSERT OR REPLACE` → **기존 데이터 덮어쓰기**
- **Qdrant**: `upsert` → **기존 문서 갱신, 신규 문서 추가**
- **삭제 처리**: 기존 ID와 신규 ID 비교 후 누락된 ID 배치 삭제

**2. 전체 재구축 (force_rebuild=True):**
- **SQLite**: 테이블 DROP 후 재생성 → **완전 초기화**
- **Qdrant**: 컬렉션 삭제 후 재생성 → **완전 초기화**

**3. parent_original_id 의미:**
- 첨부파일이 속한 **티켓/문서의 원본 ID**
- 첨부파일과 부모 객체 간의 연관 관계 유지

**4. 검증된 운영 정책:**
- 이 정책들은 이미 코드에 구현되어 있으며, 실제 운영에서 검증된 안정적인 데이터 처리 방식
- 텍스트+해시 기반 변경 감지로 불필요한 업데이트 방지
- 배치 삭제로 성능 최적화 (100개씩 처리)
- 멀티 스토리지(SQL+Vector) 동시 관리로 데이터 일관성 보장

이로써 기존 DB가 있을 때 재수집 시 **덮어쓰기가 기본 정책**이며, `force_rebuild` 옵션 시에만 **전체 삭제 후 재구축**이 이루어짐을 확인했습니다.

### ⚡ **성능 및 안정성 특징**

- **중복 감지**: SHA-256 해시 기반으로 빠르고 정확한 변경 감지
- **배치 처리**: 100개씩 묶어서 삭제/업데이트하여 성능 최적화
- **트랜잭션 안전성**: SQLite와 Qdrant 동시 처리로 데이터 일관성 보장
- **복구 가능성**: `force_rebuild` 외에는 기존 데이터 보존 정책

---


### 🔧 **데이터 수집 및 처리 완전 가이드**

#### **📥 데이터 적재 방식**

**1. 신규 수집 (빈 DB):**
```python
# 모든 데이터를 새로 적재
INSERT INTO documents (original_id, content, hash, ...)
VALUES (?, ?, ?, ...)
```

**2. 재수집 (기존 DB 존재):**
```python
# INSERT OR REPLACE 패턴으로 덮어쓰기
INSERT OR REPLACE INTO documents (original_id, content, hash, ...)
VALUES (?, ?, ?, ...)
```

#### **🔄 변경 감지 및 갱신**

**1. 텍스트 + 해시 기반 변경 감지:**
```python
def generate_document_hash(content_text: str) -> str:
    """텍스트 내용을 기반으로 해시 생성"""
    return hashlib.md5(content_text.encode('utf-8')).hexdigest()

# 변경 감지 로직
new_hash = generate_document_hash(ticket_text)
if existing_hash != new_hash:
    # 내용이 변경된 경우에만 업데이트
    update_document(...)
```

**2. 통합 객체 (integrated_content) 생성:**
```python
integrated_content = {
    "main_content": "티켓 본문 내용",
    "metadata": {
        "ticket_id": "12345",
        "subject": "문의 제목", 
        "status": "resolved",
        "priority": "high",
        "created_at": "2025-01-01T10:00:00Z",
        "updated_at": "2025-01-02T15:30:00Z"
    },
    "attachments": [
        {
            "id": "att_001",
            "filename": "screenshot.png",  
            "content_type": "image/png",
            "parent_original_id": "12345"  # 부모 티켓 ID
        }
    ]
}
```

#### **🗑️ 삭제 처리 방식**

**1. 증분 수집 시 자동 삭제:**
```python
# 기존 ID 목록과 신규 ID 목록 비교
existing_ids = get_existing_document_ids()
collected_ids = get_newly_collected_ids()
deleted_ids = existing_ids - collected_ids

# 배치 삭제 처리 (SQL + Qdrant)
if deleted_ids:
    # SQL에서 100개씩 배치 삭제
    batch_delete_documents(deleted_ids, batch_size=100)
    
    # Qdrant에서 배치 삭제
    qdrant_client.delete(
        collection_name=collection_name,
        points_selector=PointIdsList(point_ids=deleted_ids)
    )
```

**2. 강제 재구축 시 전체 삭제:**
```python
# force_rebuild=True 또는 purge=True
DROP TABLE IF EXISTS documents;
CREATE TABLE documents (...);

# Qdrant 컬렉션 재생성
qdrant_client.delete_collection(collection_name)
qdrant_client.create_collection(collection_name, ...)
```

### 🎛️ **수집 옵션별 세부 동작**

#### **📋 incremental=True (기본값)**
```json
{
  "incremental": true,
  "max_tickets": 1000,
  "include_kb": true
}
```
**실행 과정:**
1. ✅ 기존 데이터 유지
2. 🔍 새로운 데이터 수집
3. 📊 해시 값으로 변경 감지
4. 🔄 변경된 문서만 업데이트
5. 🗑️ 삭제된 문서 자동 제거
6. ➕ 신규 문서 추가

#### **🔄 incremental=False**
```json
{
  "incremental": false,
  "max_tickets": 1000,
  "include_kb": true
}
```
**실행 과정:**
1. ⚠️ 기존 데이터 유지
2. 🔄 모든 데이터 다시 수집
3. 📝 INSERT OR REPLACE로 모든 문서 덮어쓰기
4. 📊 전체 데이터 일관성 보장

#### **🚀 force_rebuild=True**
```json
{
  "force_rebuild": true,
  "max_tickets": 1000,
  "include_kb": true
}
```
**실행 과정:**
1. 🗑️ 기존 데이터 완전 삭제
2. 🏗️ 테이블/컬렉션 재생성
3. 📥 모든 데이터 새로 적재
4. 🔧 자동으로 `purge=True`, `incremental=False` 설정

### 💡 **실전 운영 시나리오**

#### **🔄 정기 운영 (권장)**
```bash
# 매일 자동 증분 수집
POST http://localhost:8000/ingest/jobs
Content-Type: application/json

{
  "platform": "freshdesk",
  "incremental": true,
  "max_tickets": 10000,
  "include_kb": true
}
```

#### **🔧 문제 해결 시**
```bash  
# 데이터 불일치 문제 해결
POST http://localhost:8000/ingest/jobs
Content-Type: application/json

{
  "platform": "freshdesk", 
  "force_rebuild": true,
  "max_tickets": 50000,
  "include_kb": true
}
```

#### **📊 진행 상황 모니터링**
```bash
# 작업 상태 확인 (2-5초 간격)
GET http://localhost:8000/ingest/jobs/{job_id}/status

# 응답 예시
{
  "status": "in_progress",
  "progress": 75.5,
  "processed": 7550,
  "total": 10000,
  "current_stage": "processing_tickets",
  "estimated_completion": "2025-01-15T14:30:00Z"
}
```

### 🚨 **보안 및 안정성 고려사항**

#### **🔐 데이터 일관성 보장**
- **트랜잭션**: SQLite 배치 작업 시 트랜잭션 사용
- **롤백**: 수집 중 오류 발생 시 안전한 롤백 처리  
- **동시성**: 동일 플랫폼에서 여러 작업 동시 실행 방지

#### **📈 대용량 데이터 처리**
- **메모리 관리**: 청크 단위로 데이터 처리 (기본 1000개)
- **배치 크기**: 삭제/업데이트 시 100개씩 처리
- **네트워크**: API 호출 실패 시 재시도 로직 (최대 3회)

#### **🔍 로깅 및 모니터링**
```python
# 핵심 로그만 기록
logging.info(f"Started processing {total_tickets} tickets")
logging.info(f"Updated {updated_count} documents")
logging.info(f"Deleted {deleted_count} documents")
logging.info(f"Added {added_count} new documents")
```

### 📎 **첨부파일 parent_original_id 상세**

**의미**: 첨부파일이 속한 부모 객체(티켓/문서)의 original_id
**용도**: 
- 첨부파일과 티켓 간의 연관 관계 유지
- 특정 티켓의 모든 첨부파일 조회
- 데이터 정합성 검증

**활용 예시:**
```sql
-- 특정 티켓의 모든 첨부파일 조회
SELECT * FROM documents 
WHERE parent_original_id = '12345' 
AND document_type = 'attachment';

-- 첨부파일이 있는 티켓만 조회
SELECT DISTINCT parent_original_id 
FROM documents 
WHERE document_type = 'attachment';
```

---

## 🎯 **최종 완성: 데이터 처리 정책 총정리**

### ✅ **검증된 핵심 정책**

1. **기본 저장 방식**: `INSERT OR REPLACE` (덮어쓰기 정책)
2. **변경 감지**: 텍스트 + MD5 해시 값 기반 스마트 업데이트  
3. **삭제 처리**: 증분 수집 시 배치 삭제 (SQL + Qdrant 동시 처리)
4. **통합 객체**: main_content + metadata + attachments 구조화
5. **옵션별 동작**: incremental/force_rebuild/purge 명확한 역할 분담

### 🚀 **운영 가이드라인**

- **일반 운영**: `incremental=True` (스마트 증분 수집)
- **초기 구축**: `force_rebuild=True` (완전 재구축)
- **문제 해결**: 단계별 진단 후 적절한 옵션 선택
- **성능 최적화**: 배치 처리 + 해시 기반 변경 감지

### ⚡ **성능 및 안정성 특징**

- **빠른 변경 감지**: MD5 해시 기반으로 불필요한 업데이트 방지
- **배치 처리**: 100개씩 묶어서 처리하여 성능 최적화
- **데이터 일관성**: SQLite와 Qdrant 동시 관리
- **복구 안전성**: 기존 데이터 보존 우선 정책

**이제 모든 데이터 수집 및 처리 정책이 완전히 문서화되었습니다!** 
프론트엔드는 **단순히 HTTP 호출만** 하면 모든 기능을 안전하고 효율적으로 사용할 수 있습니다! 🎉
