# 📚 AI Instructions Directory Index

> **🚀 AI 첫 참조 가이드**: 이 파일 → `core/quick-reference.instructions.md` → 작업별 지침서

## 🎯 즉시 참조 (우선순위 순)

### 🔥 필수 시작점
1. **[Quick Reference](./core/quick-reference.instructions.md)** ⭐ - 핵심 패턴 (5분 읽기)
2. **[Global Instructions](./core/global.instructions.md)** - 전역 규칙과 원칙

### 🚨 최신 업데이트 (2025-06-22)
- **[Pipeline Updates](./data/pipeline-updates-20250622.instructions.md)** 🔥 - 멀티테넌트 파이프라인 완성
- **[Session Summary](./core/session-summary-20250622.instructions.md)** - 오늘 해결한 문제들
- **[Multitenant Security](./core/multitenant-security.instructions.md)** - 업데이트된 보안 정책

## 📂 디렉터리별 가이드

## 🏗️ Core - 필수 참조 파일들
**🎯 모든 작업 전 필수 확인**

| 파일 | 용도 | 크기 | 참조 시점 |
|------|------|------|-----------|
| **[Quick Reference](./core/quick-reference.instructions.md)** | 핵심 패턴 요약 | ~8KB | 모든 작업 시작 |
| **[Global Instructions](./core/global.instructions.md)** | 전역 개발 원칙 | ~15KB | 새 기능 개발 시 |
| **[Multitenant Security](./core/multitenant-security.instructions.md)** | 보안 정책 | ~20KB | 데이터 처리 시 |
| **[System Architecture](./core/system-architecture.instructions.md)** | 전체 구조 | ~25KB | 아키텍처 변경 시 |

## 💻 Development - 개발 패턴 가이드
**🔧 개발 작업 시 참조**

| 주요 파일 | 설명 |
|-----------|------|
| `fdk-development-patterns.instructions.md` | FDK 프론트엔드 개발 |
| `backend-implementation-patterns.instructions.md` | FastAPI 백엔드 패턴 |
| `error-handling-debugging.instructions.md` | 디버깅 및 오류 처리 |
| `api-architecture-file-structure.instructions.md` | API 구조 설계 |

## 📊 Data - 데이터 파이프라인 가이드
**📈 데이터 처리 작업 시 참조**

| 파일 | 중요도 | 설명 |
|------|--------|------|
| **[API 엔드포인트 가이드](./data/api-endpoints-data-ingestion-guide.instructions.md)** | 🔥 **NEW** | **실전 API 사용법 (시행착오 기반)** |
| **[Pipeline Updates 2025-06-22](./data/pipeline-updates-20250622.instructions.md)** | 🔥 최우선 | 최신 파이프라인 변경사항 |
| **[Data Workflow](./data/data-workflow.instructions.md)** | ⭐ 필수 | 전체 데이터 처리 흐름 |
| **[Vector Storage Core](./data/vector-storage-core.instructions.md)** | ⭐ 핵심 | 벡터DB 핵심 패턴 |
| **[Storage Abstraction](./data/storage-abstraction-core.instructions.md)** | ⭐ 핵심 | 저장소 추상화 패턴 |
| `data-collection-patterns.instructions.md` | 📋 참조 | 데이터 수집 전략 |
| `vector-search-advanced.instructions.md` | 🔍 고급 | 고급 검색 기능 |

## 🎯 Specialized - 특화 기능 가이드
**🚀 특정 기능 구현 시 참조**

| 기능 영역 | 주요 파일 |
|-----------|-----------|
| **LLM 처리** | `llm-conversation-filtering-strategy.instructions.md` |
| **멀티플랫폼** | `platform-adapters-multiplatform.instructions.md` |
| **모니터링** | `monitoring-testing-strategy.instructions.md` |
| **확장성** | `scalability-roadmap-implementation.instructions.md` |

---

## 🎯 AI 참조 가이드라인

### 📋 작업 시나리오별 참조 경로

#### 🚀 **새 기능 개발**
```mermaid
AI 시작 → Quick Reference → Development 패턴 → 특화 기능
```
1. `core/quick-reference.instructions.md` (5분)
2. `development/` 관련 패턴 파일 (10분)
3. `specialized/` 해당 기능 파일 (필요시)

#### 🐛 **디버깅 및 오류 수정**
```mermaid
문제 발생 → Error Handling → Quick Reference → 관련 영역
```
1. `development/error-handling-debugging.instructions.md`
2. `core/quick-reference.instructions.md`
3. 해당 기능 영역 파일

#### 📊 **데이터 처리 작업**
```mermaid
데이터 작업 → Pipeline Updates → Data Workflow → 세부 패턴
```
1. `data/pipeline-updates-20250622.instructions.md` ⭐ **최신**
2. `data/data-workflow.instructions.md` (전체 흐름)
3. 구체적 작업별 data/ 하위 파일

#### 🎯 **특화 기능 구현**
```mermaid
특화 기능 → Specialized 파일 → Development 패턴 → Quick Reference
```
1. `specialized/` 해당 기능 파일
2. `development/` 관련 구현 패턴  
3. `core/quick-reference.instructions.md`

### ⚡ 효율적 참조 원칙

| 원칙 | 설명 | 예시 |
|------|------|------|
| **Always Start** | 항상 Quick Reference부터 | `core/quick-reference.instructions.md` |
| **Latest First** | 최신 업데이트 우선 확인 | `data/pipeline-updates-20250622.instructions.md` |
| **Domain Specific** | 해당 영역 메인 파일 참조 | data/ → `data-workflow.instructions.md` |
| **Cross Reference** | "See Also" 섹션 활용 | 링크 따라가기 |
| **Size Awareness** | 파일 크기 고려한 읽기 | 큰 파일은 섹션별로 |

### 📊 파일 크기 & 읽기 시간 가이드

| 카테고리 | 크기 | 읽기 시간 | 용도 |
|----------|------|-----------|------|
| **Quick Reference** | ~8KB | 5분 | 빠른 패턴 확인 |
| **Development** | 15-25KB | 10-15분 | 구현 가이드 |
| **Data** | 15-30KB | 15-20분 | 워크플로우 포함 |
| **Specialized** | 20-35KB | 20-25분 | 특화 기능 상세 |

---

## 🔄 최신 업데이트 & 테스트 가이드

### � **2025-06-22 완료 사항** ✅

#### 🚨 **멀티테넌트 데이터 파이프라인 완성**
- ✅ **표준 4개 헤더 API 통합** (X-Company-ID, X-Platform, X-Domain, X-API-Key)
- ✅ **멀티테넌트 DB 정책** (회사별 SQLite 파일 분리)
- ✅ **fetcher 파라미터 일관성** (company_id 제거, 표준 파라미터만 사용)
- ✅ **ingest 엔드포인트 준비 완료** (100건 테스트 데이터 수집 가능)

#### 🧪 **즉시 실행 가능한 테스트**
```bash
# 1. 백엔드 서버 시작
cd backend && source venv/bin/activate && python -m uvicorn api.main:app --reload

# 2. ingest 엔드포인트 테스트 (100건 데이터 수집)
curl -X POST "http://localhost:8000/ingest" \
  -H "Content-Type: application/json" \
  -H "X-Company-ID: your_company" \
  -H "X-Platform: freshdesk" \
  -H "X-Domain: your_company.freshdesk.com" \
  -H "X-API-Key: your_api_key" \
  -d '{"max_tickets": 100, "include_kb": true}'

# 3. 데이터베이스 파일 확인
ls -la backend/your_company_freshdesk.db  # 회사별 DB 파일 생성 확인
```

#### 📚 **새로 추가된 핵심 지침서**
- **[Pipeline Updates 2025-06-22](./data/pipeline-updates-20250622.instructions.md)** 🔥 - 완전한 변경사항 가이드
- **[Session Summary 2025-06-22](./core/session-summary-20250622.instructions.md)** - 문제 해결 요약
- **[Updated Multitenant Security](./core/multitenant-security.instructions.md)** - 최신 보안 정책

### 🎯 **다음 단계 (준비 완료)**
- [ ] **ingest 엔드포인트 100건 테스트 실행** (위 curl 명령어 사용)
- [ ] **데이터베이스 확인** (티켓/첨부파일/KB 데이터 정상 저장 검증)
- [ ] **검색 API 테스트** (수집된 데이터로 유사 티켓 검색)
- [ ] **프론트엔드 연동** (FDK 앱에서 백엔드 API 호출)

---

## � 파일 관리 & 최적화 상태

### ✅ **현재 구조 최적화 완료**
- **총 지침서 수**: 25개 (적정)
- **평균 파일 크기**: 20KB (최적)
- **참조 깊이**: 최대 3단계 (효율적)
- **크로스 링크**: 90% 연결 (양호)

### 🎯 **AI 참조 효율성 지표**
- **첫 정보 접근**: 1단계 (Quick Reference)
- **심화 정보 접근**: 2-3단계 (영역별 파일)
- **최신 정보 접근**: 1단계 (Pipeline Updates)
- **문제 해결**: 2단계 (Error Handling → 관련 영역)

---

## 📞 **긴급 참조 (AI용)**

### � **문제 발생 시 즉시 참조**
1. **서버 실행 오류** → `development/error-handling-debugging.instructions.md`
2. **데이터 파이프라인 문제** → `data/pipeline-updates-20250622.instructions.md`
3. **API 엔드포인트 문제** → `core/quick-reference.instructions.md`
4. **보안/권한 문제** → `core/multitenant-security.instructions.md`

### 📋 **체크리스트 (AI 작업 전)**
- [ ] Quick Reference 확인 (5분)
- [ ] 최신 Pipeline Updates 확인 (해당시)
- [ ] 작업 영역별 지침서 식별
- [ ] 관련 크로스 링크 확인
- [ ] 파일 크기 고려한 읽기 전략 수립

---

**📚 이 인덱스는 AI와 개발자의 효율적인 작업을 위해 지속적으로 최적화됩니다.**
