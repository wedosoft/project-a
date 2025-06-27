---
applyTo: "**"
priority: "highest"
lastUpdated: "2025-06-26"
---

# 🚀 현재 프로젝트 상태 - AI 참조 가이드

_최신 상황 반영 완료 (2025-06-26)_

## 🚨 **AI 필수 준수사항 - 작업 프로세스**

### ⚡ **모든 작업은 3단계 프로세스 준수 (예외 없음)**
1. **📋 제안 (Proposal)**: 상세한 변경사항 설명 및 영향도 분석
2. **✅ 컨펌 (Confirmation)**: 사용자 승인 대기 (필수)
3. **🔧 단계적 작업 (Step-by-step)**: 컨펌 후에만 실행

### 🔒 **절대 금지사항**
- 사전 제안 없는 코드 변경, 파일 생성/삭제
- 컨펌 없는 시스템 설정 변경
- 임의 판단에 의한 작업 진행

---

## 🎯 **즉시 참조용 - 현재 프로젝트 핵심 상태**

### 📋 **프로젝트 정의**
- **목적**: Freshdesk 기반 멀티테넌트 RAG 시스템
- **현재 단계**: ORM 통합 완료, 데이터 중복 저장 문제 해결 중
- **아키텍처**: SQLite(개발) + PostgreSQL(운영) + Qdrant + Redis
- **주요 변화**: 멀티플랫폼 제거 → Freshdesk 전용, ORM 도입, 백엔드 구조 정리

### 🔥 **현재 진행 중인 핵심 이슈**
1. **데이터 중복 저장 문제**: `integrated_objects` 테이블에서 동일 `original_id` 중복 발생
2. **백엔드 구조 정리**: 중복 디렉터리 통합 (`backend/freshdesk/` → `core/platforms/freshdesk/`)
3. **ORM vs SQLite 마이그레이션**: USE_ORM 플래그 기반 점진적 전환

### ⚠️ **AI 작업 시 필수 주의사항**
- **기존 코드 90% 재활용**: 전면 재작성 금지, 점진적 개선만
- **멀티테넌트 필수**: 모든 데이터에 company_id 자동 태깅
- **표준 4개 헤더**: X-Company-ID, X-Platform, X-Domain, X-API-Key 
- **중복 저장 방지**: UPSERT 패턴 적용 필수

---

## 📊 **완료된 주요 마일스톤**

### ✅ **ORM 통합 완성** (2025-06-26)
```python
# 현재 상태: USE_ORM=true 활성화
# 15개 SQLAlchemy 모델 완성
# Repository 패턴 구현
# 마이그레이션 레이어 완성
```

### ✅ **멀티테넌트 SaaS 아키텍처 완성**
```sql
-- 테넌트별 완전 격리
companies, company_settings, platform_configs
-- 데이터베이스 기반 설정 관리 (환경변수 최소화)
```

### ✅ **통합 객체 중심 아키텍처 완성**
```python
# 모든 데이터가 integrated_objects 테이블 중심
# LLM 기반 첨부파일 선택기 구현
# 벡터 검색 통합 완료
```

### ✅ **API 헤더 표준화 완성**
```python
# 모든 API 엔드포인트가 표준 4개 헤더만 사용
# 레거시 헤더/환경변수 완전 제거
# FastAPI Swagger 문서 정리
```

---

## 🔧 **현재 기술 스택 & 구조**

### 🏗️ **아키텍처 구성**
```
Frontend (FDK) → FastAPI → SQLAlchemy ORM → SQLite/PostgreSQL
                     ↓
                 Qdrant (벡터DB) + Redis (캐시)
```

### 📂 **백엔드 디렉터리 구조** (정리 중)
```
backend/
├── api/                    # FastAPI 라우터들
├── core/                   # 핵심 비즈니스 로직
│   ├── database/          # SQLAlchemy ORM 모델
│   ├── ingest/            # 데이터 수집 파이프라인
│   ├── llm/               # LLM 통합 관리
│   ├── platforms/         # Freshdesk 어댑터
│   └── search/            # 벡터 검색
├── config/                # 설정 파일들 (정리 중)
└── tests/                 # 테스트
```

### 🔑 **환경 설정**
```bash
# 현재 개발 환경
USE_ORM=true              # ORM 모드 활성화
LOG_LEVEL=ERROR           # 디버그 로그 제거
DATABASE_TYPE=sqlite      # 개발 환경
ENVIRONMENT=development   

# 운영 환경 (준비 완료)
DATABASE_URL=postgresql://... # 설정 시 PostgreSQL 자동 전환
```

---

## 🚨 **현재 해결 중인 문제**

### 1️⃣ **데이터 중복 저장 문제** (최우선)
**증상**: 같은 `original_id`에 대해 여러 레코드 생성
```sql
-- 현재 발생 중인 문제
SELECT original_id, object_type, COUNT(*) as count
FROM integrated_objects
GROUP BY original_id, object_type
HAVING COUNT(*) > 1;
```

**원인 추정**:
- `store_integrated_object_to_sqlite` 함수에서 ORM과 SQLite 둘 다 저장 시도
- UNIQUE 제약 조건 무시하는 INSERT 로직
- 중복 체크 미흡

**해결 방향**:
- UPSERT (INSERT OR REPLACE) 패턴 적용
- USE_ORM=false일 때 SQLite만 사용하도록 수정
- 중복 체크 로직 강화

### 2️⃣ **백엔드 구조 정리** (진행 중)
**문제**: 중복된 기능들
```
backend/freshdesk/         # 중복
core/platforms/freshdesk/  # 메인
backend/data/              # 중복
core/data/                 # 메인
```

**해결 계획**: 
- Phase 1: Freshdesk 통합
- Phase 2: Data 통합
- Phase 3: Config 재구성

---

## 📋 **AI 작업 시 필수 체크포인트**

### 🔍 **작업 시작 전 확인사항**
1. **현재 USE_ORM 상태 확인**: `echo $USE_ORM`
2. **데이터베이스 연결 확인**: `db.cursor()` 에러 여부
3. **멀티테넌트 격리**: company_id 포함 여부
4. **표준 헤더 사용**: 4개 헤더 필수

### ⚠️ **절대 금지 사항**
- **전면 재작성**: 기존 검증된 코드 90% 이상 재활용 필수
- **멀티플랫폼 추가**: Freshdesk 전용으로 고정됨
- **환경변수 의존성**: 표준 헤더 기반으로 완전 전환됨
- **ORM 무시**: USE_ORM=true 상태에서 SQLite 직접 쿼리 금지

### 📝 **코딩 원칙**
```python
# ✅ 올바른 패턴 - 기존 함수 개선
def improved_function():
    existing_logic = existing_function()  # 기존 코드 재활용
    enhanced_logic = add_company_id_tagging(existing_logic)
    return enhanced_logic

# ❌ 피해야 할 패턴 - 전면 재작성
def completely_new_function():
    # 완전히 새로운 로직 (금지)
    pass
```

---

## 🎯 **다음 세션 우선순위**

### 🔥 **즉시 해결 필요** (Priority 1)
1. **중복 저장 문제 해결**
   - `store_integrated_object_to_sqlite` 함수 수정
   - UPSERT 패턴 적용
   - 중복 데이터 정리

### 📊 **구조 정리** (Priority 2)
1. **백엔드 디렉터리 통합**
   - `backend/freshdesk/` → `core/platforms/freshdesk/`
   - 중복 기능 제거
   - Import 경로 수정

### 🧪 **검증 및 테스트** (Priority 3)
1. **End-to-End 파이프라인 테스트**
   - 데이터 수집 → 저장 → 요약 → 벡터화
   - 멀티테넌트 격리 검증
   - API 표준 헤더 동작 확인

---

## 💡 **새 세션 시작용 프롬프트**

```
안녕하세요! Freshdesk 멀티테넌트 RAG 시스템을 이어서 진행하겠습니다.

**현재 상황:**
- ORM 통합 완료 (USE_ORM=true 활성화)
- 멀티테넌트 SaaS 아키텍처 완성
- 통합 객체 중심 아키텍처 완성
- API 헤더 표준화 완성

**해결이 필요한 문제:**
integrated_objects 테이블에서 데이터 중복 저장 문제가 발생하고 있습니다. 
같은 original_id에 대해 중복 레코드가 생성되고 있어서, 
store_integrated_object_to_sqlite 함수에 UPSERT 패턴 적용이 필요합니다.

**환경 설정:**
- USE_ORM=true
- LOG_LEVEL=ERROR  
- SQLite 개발 환경
- 표준 4개 헤더 (X-Company-ID, X-Platform, X-Domain, X-API-Key)

이 중복 저장 문제를 해결하고 end-to-end 데이터 파이프라인을 완성해 주세요.
```

---

## 📚 **관련 참조 문서**

### 📄 **프로젝트 문서** (`/docs/`)
- `ORM_INTEGRATION_SUCCESS_REPORT.md`: ORM 통합 완료 보고서
- `INTEGRATED_ARCHITECTURE_COMPLETION_REPORT.md`: 통합 아키텍처 완성
- `MULTITENANT_ARCHITECTURE_GUIDE.md`: 멀티테넌트 구조 가이드
- `BACKEND_CLEANUP_PLAN.md`: 백엔드 구조 정리 계획
- `SESSION_HANDOVER_GUIDE.md`: 세션 인계 가이드

### 🔗 **지침서 연결**
- `quick-reference.instructions.md`: 핵심 패턴 요약
- `security-data-purge.instructions.md`: GDPR 대응 보안 기능
- `api-complete-reference.instructions.md`: 완성된 API 엔드포인트
- `backend-implementation-patterns.instructions.md`: 백엔드 구현 패턴

---

**📝 이 문서는 현재 프로젝트의 최신 상태를 AI가 즉시 참조할 수 있도록 정리된 핵심 가이드입니다.**
