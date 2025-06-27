# 🚨 현재 해결 중인 이슈들

_최종 업데이트: 2025-06-27_

## 🎯 **최우선 해결 이슈** (Priority 1)

### 1️⃣ **API 엔드포인트 현황 파악 및 문제 해결**
- **상태**: 🔴 진행 중
- **문제**: `/ingest` API가 작동하지 않음 (사용자 리포트)
- **조사 필요**: 
  - 실제 존재하는 API 엔드포인트 확인
  - ORM 적용 여부 확인
  - 에러 로그 분석
- **참조**: NEXT_SESSION_GUIDE에서 언급한 `/ingest/sync-summaries`는 실제로 존재하지 않음

### 2️⃣ **지침서 정리 및 최신화**
- **상태**: 🟡 계획 중
- **문제**: 
  - `.github/instructions/` (25개 파일) vs `docs/` (45개+ 파일) 정보 혼재
  - 구버전 vs 신버전 헤더 정보 혼재
  - AI가 잘못된 정보 참조하는 문제
- **해결 방향**:
  - 마스터 현황 문서 생성
  - 구버전 정보 archived 폴더로 이동
  - AI 참조용 Quick Start 가이드 생성

## 📋 **중요 이슈** (Priority 2)

### 3️⃣ **docs 폴더 역할 명확화**
- **상태**: 🟡 계획 중  
- **문제**: docs 폴더에 너무 많은 문서 (45개+)
- **제안**:
  - 현재 유효한 문서 식별
  - 구버전 문서들 정리
  - 문서 분류 체계 수립

### 4️⃣ **헤더 표준 확정**
- **상태**: 🟡 확인 필요
- **혼재 상황**:
  - 지침서: X-Company-ID, X-Platform, X-Domain, X-API-Key (4개)
  - 실제 코드: X-Tenant-ID, X-Platform (2개?)
  - NEXT_SESSION_GUIDE: X-Tenant-ID, X-Platform (2개)
- **해결**: 실제 코드베이스 확인 후 결정

## ⚡ **즉시 실행 가능한 작업**

### 🔍 **Phase 1: 현황 진단** (오늘)
```bash
# 1. API 서버 실행 테스트
cd backend && source venv/bin/activate
python -m uvicorn api.main:app --reload

# 2. 실제 엔드포인트 확인
curl -X GET "http://localhost:8000/docs"  # Swagger UI

# 3. 헤더 구조 확인
grep -r "X-Tenant-ID\|X-Company-ID" backend/api/
```

### 📚 **Phase 2: 지침서 정리** (내일)
1. 현재 유효한 정보 식별
2. 마스터 현황 문서 생성  
3. 구버전 문서들 archived 이동
4. AI Quick Reference 업데이트

### 🧹 **Phase 3: docs 폴더 정리** (이후)
1. 문서 분류 (current / archived / deprecated)
2. 중복 제거
3. 역할별 문서 구조 재정립

---

## 📝 **작업 기록**

### 2025-06-27
- ✅ TaskMaster 비활성화 완료
- ✅ tasks → archived_tasks 이동
- ✅ 문서 기반 관리 체계 구축 완료
- ✅ 마스터 현황 문서 생성 (docs/MASTER_STATUS.md)
- ✅ AI 지침서 인덱스 업데이트
- 🔄 API 현황 진단 시작

---

## 🔗 **관련 문서**

- `NEXT_SESSION_GUIDE-20250627-2118.md` - 이전 세션 작업 계획
- `.github/instructions/INDEX.md` - AI 지침서 인덱스
- `docs/` - 프로젝트 문서들 (정리 필요)
- `archived_tasks/` - 기존 TaskMaster 태스크들
