---
applyTo: "**"
---

# 🔐 보안 & 데이터 완전 삭제 지침서

_GDPR 대응 및 사용자 데이터 보안 관리 - 2025-06-23 완성_

## 🎯 **핵심 요약**

### 🚨 **완전한 데이터 초기화 구현**
사용자 데이터 민감성을 고려한 **완전하고 안전한 삭제** 기능 완성:
- 🗄️ **SQLite 데이터**: 티켓, 지식베이스, 요약 등
- 🔍 **벡터 DB**: Qdrant 임베딩 및 메타데이터  
- 💾 **캐시 데이터**: Redis, 메모리 캐시
- 🔐 **AWS Secrets Manager**: API 키, 인증 토큰 등

### 🛡️ **보안 검증 단계**
1. **토큰 검증**: 일일 보안 토큰 생성 및 확인
2. **액션 검증**: purge_all, reset_company, delete_platform
3. **백업 생성**: 삭제 전 자동 백업 (선택사항)
4. **감사 로그**: 모든 작업 기록 및 추적

---

## 🚀 **API 엔드포인트**

### 1️⃣ **보안 토큰 생성**
```http
POST /ingest/security/generate-token
Headers: X-Company-ID, X-Platform
```

**응답 예시:**
```json
{
  "security_token": "DELETE_company123_freshdesk_20250623",
  "valid_until": "20250623 23:59:59",
  "usage_example": {
    "confirmation_token": "DELETE_company123_freshdesk_20250623",
    "action": "purge_all",
    "reason": "GDPR 잊혀질 권리 요청",
    "create_backup": true,
    "include_secrets": true
  },
  "warning": "⚠️ 이 토큰을 사용한 삭제는 복구할 수 없습니다!"
}
```

### 2️⃣ **데이터 완전 삭제**
```http
POST /ingest/security/purge-data
Headers: X-Company-ID, X-Platform
Body: {
  "confirmation_token": "DELETE_company123_freshdesk_20250623",
  "action": "purge_all",
  "reason": "GDPR 요청",
  "create_backup": true,
  "include_secrets": true,
  "aws_region": "us-east-1"
}
```

---

## 📊 **삭제 액션 타입**

| 액션 | 범위 | 사용 사례 |
|------|------|-----------|
| `purge_all` | 모든 데이터 | GDPR 완전 삭제, 계약 종료 |
| `reset_company` | 특정 회사 | 회사별 데이터 정리 |
| `delete_platform` | 특정 플랫폼 | 플랫폼별 데이터 정리 |

## 🔒 **AWS Secrets Manager 처리**

### 자동 패턴 매칭
시스템이 자동으로 다음 패턴의 시크릿을 탐지:
```
*company_id*
*platform*
company_id-*
platform-*
*-company_id-*
*-platform-*
```

### 삭제 옵션
- **기본 (안전)**: 30일 복구 기간 후 삭제
- **강제 (위험)**: 즉시 영구 삭제 (`force_delete: true`)

---

## 🛠️ **작업 제어 (pause/resume/cancel)**

### 백그라운드 작업 제어
```http
POST /ingest/jobs/{job_id}/control
Body: {"action": "pause|resume|cancel"}
```

### 제어 가능 여부
- ✅ **백그라운드 작업** (/ingest/jobs): 완전 제어 지원
- ❌ **즉시 실행** (/ingest): 제어 불가 (동기식)

### 상태 확인
```http
GET /ingest/jobs/{job_id}
Response: {
  "can_pause": true,
  "can_resume": false,
  "can_cancel": true
}
```

---

## 🎯 **사용 시나리오**

### 1️⃣ **GDPR "잊혀질 권리" 요청**
```bash
# 1. 토큰 생성
curl -X POST "http://localhost:8000/ingest/security/generate-token" \
  -H "X-Company-ID: customer123" \
  -H "X-Platform: freshdesk"

# 2. 완전 삭제 실행
curl -X POST "http://localhost:8000/ingest/security/purge-data" \
  -H "X-Company-ID: customer123" \
  -H "X-Platform: freshdesk" \
  -H "Content-Type: application/json" \
  -d '{
    "confirmation_token": "DELETE_customer123_freshdesk_20250623",
    "action": "purge_all",
    "reason": "GDPR Article 17 - Right to erasure",
    "create_backup": true,
    "include_secrets": true
  }'
```

### 2️⃣ **보안 사고 시 긴급 대응**
```json
{
  "confirmation_token": "DELETE_company_platform_date",
  "action": "purge_all",
  "reason": "Security incident - immediate data purge required",
  "create_backup": false,
  "force_delete": true,
  "include_secrets": true
}
```

### 3️⃣ **대량 데이터 처리 중 중단**
```bash
# 작업 일시정지
curl -X POST "http://localhost:8000/ingest/jobs/job123/control" \
  -H "X-Company-ID: company123" \
  -d '{"action": "pause"}'

# 작업 재개
curl -X POST "http://localhost:8000/ingest/jobs/job123/control" \
  -H "X-Company-ID: company123" \
  -d '{"action": "resume"}'

# 작업 취소
curl -X POST "http://localhost:8000/ingest/jobs/job123/control" \
  -H "X-Company-ID: company123" \
  -d '{"action": "cancel"}'
```

---

## ⚠️ **중요 주의사항**

### 🔒 **보안**
- **토큰 유효기간**: 당일만 유효 (자정 만료)
- **감사 로그**: 모든 삭제 작업 기록
- **백업 권장**: 중요 데이터는 반드시 백업 후 삭제

### 🔥 **복구 불가 작업**
- `force_delete: true` 사용 시 **즉시 영구 삭제**
- AWS Secrets Manager 강제 삭제 시 **복구 불가**
- SQLite/벡터 DB 삭제 시 **백업 없으면 복구 불가**

### 📋 **감사 추적**
모든 삭제 작업은 다음 정보와 함께 기록:
```json
{
  "action": "data_purge",
  "company_id": "company123",
  "platform": "freshdesk",
  "deleted_counts": {
    "sqlite_records": 1250,
    "vector_points": 890,
    "cache_keys": 45,
    "aws_secrets": 3
  },
  "backup_info": {...},
  "executed_at": "2025-06-23T10:30:00Z",
  "user_agent": "api_request"
}
```

---

## 🎯 **프론트엔드 통합**

### React 컴포넌트 예시
```javascript
// 보안 삭제 컴포넌트
const SecurityPanel = () => {
  const [token, setToken] = useState(null);
  const [confirmText, setConfirmText] = useState('');
  
  const generateToken = async () => {
    const response = await fetch('/api/ingest/security/generate-token', {
      method: 'POST',
      headers: {
        'X-Company-ID': companyId,
        'X-Platform': 'freshdesk'
      }
    });
    const data = await response.json();
    setToken(data.security_token);
  };
  
  const purgeData = async () => {
    if (confirmText !== 'DELETE ALL DATA') return;
    
    await fetch('/api/ingest/security/purge-data', {
      method: 'POST',
      headers: {
        'X-Company-ID': companyId,
        'X-Platform': 'freshdesk',
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        confirmation_token: token,
        action: 'purge_all',
        reason: 'User requested data deletion',
        create_backup: true,
        include_secrets: true
      })
    });
  };
  
  return (
    <div className="security-panel">
      <button onClick={generateToken}>Generate Security Token</button>
      <input 
        value={confirmText} 
        onChange={(e) => setConfirmText(e.target.value)}
        placeholder="Type 'DELETE ALL DATA' to confirm"
      />
      <button 
        onClick={purgeData}
        disabled={!token || confirmText !== 'DELETE ALL DATA'}
        className="danger-button"
      >
        🚨 Permanently Delete All Data
      </button>
    </div>
  );
};
```

### 작업 제어 컴포넌트
```javascript
const JobController = ({ jobId }) => {
  const [jobStatus, setJobStatus] = useState(null);
  
  const controlJob = async (action) => {
    await fetch(`/api/ingest/jobs/${jobId}/control`, {
      method: 'POST',
      headers: {
        'X-Company-ID': companyId,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ action })
    });
    checkJobStatus();
  };
  
  return (
    <div className="job-controls">
      <button 
        onClick={() => controlJob('pause')}
        disabled={!jobStatus?.can_pause}
      >
        ⏸️ Pause
      </button>
      <button 
        onClick={() => controlJob('resume')}
        disabled={!jobStatus?.can_resume}
      >
        ▶️ Resume
      </button>
      <button 
        onClick={() => controlJob('cancel')}
        disabled={!jobStatus?.can_cancel}
      >
        ⏹️ Cancel
      </button>
    </div>
  );
};
```

이제 모든 보안 및 데이터 삭제 기능이 완전히 구현되어 있어서, 프론트엔드는 **단순히 API 호출만** 하면 됩니다! 🎉
