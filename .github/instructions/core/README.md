# 📚 프로젝트 지침서 가이드

_AI 참조 최적화를 위한 지침서 구조 및 사용법 (2025.01.20 업데이트)_

## 🚀 **즉시 참조 - Quick Reference**

### 📋 **quick-reference.instructions.md** ⭐ **NEW**

**목적**: AI가 가장 자주 참조하는 핵심 패턴만 500라인 이하로 정리  
**참조 시기**: 모든 개발 작업의 첫 번째 참조  
**즉시 확인 가능**:

- 핵심 아키텍처 및 데이터 흐름
- FDK/백엔드 필수 구현 패턴
- 8개 핵심 API 엔드포인트
- 멀티테넌트 보안 체크리스트
- 필수 환경 변수 및 디버깅 명령어

---

## 🎯 지침서 구조 개요

이 프로젝트의 지침서는 **AI가 효율적으로 참조**할 수 있도록 **계층적 구조**로 정리되어 있습니다:

### 🔄 **참조 순서 (AI 권장)**

1. **🚀 quick-reference.instructions.md** - 모든 작업의 첫 참조
2. **📚 global.instructions.md** - 공통 원칙 확인
3. **🛠️ 특화 지침서** - 구체적 구현 시 참조
4. **📖 상세 지침서** - 복잡한 구현 시 참조

### 📊 **지침서 크기 최적화 현황**

- **🟢 적정 크기 (500라인 이하)**: quick-reference, global, 특화 지침서들
- **🔴 과대 크기 (1000라인 이상)**: implementation-guide, data-workflow, core-architecture
- **📋 개선 계획**: 거대 지침서는 토픽별 분할 예정 (Phase 2)

---

## 📚 **핵심 지침서 (Core Instructions)**

### 🏗️ 1. **global.instructions.md** (181줄 - 🟢 적정)

**역할**: 전체 개발 원칙, 파일 관리, 모듈화 아키텍처  
**참조 시기**: 모든 개발 작업의 기본 원칙  
**주요 내용**:

- **파일 및 버전 관리 지침**: 원본 파일명 유지, 사전 컨펌 원칙
- **모듈화 아키텍처**: LLM/데이터 수집 모듈 분리 구조
- **가상환경 원칙**: Python/Node.js 의존성 관리
- **커뮤니케이션 톤**: 한국어 사용, 정중한 존댓말

---

## 🛠️ **특화 지침서 (Specialized Instructions)**

### 🧠 4. **llm-conversation-filtering-strategy.instructions.md** (239줄 - � 적정)

**역할**: LLM 대화 필터링 전략 및 다국어 지원  
**참조 시기**: LLM 요약 생성, 대화 처리, 다국어 환경  
**주요 내용**:

- **기존 문제점 분석**: 5개 대화 제한의 한계
- **3단계 스마트 필터링**: 노이즈 제거 → 중요도 평가 → 토큰 최적화
- **다국어 키워드**: 한국어/영어 중요도 판별
- **성능 지표**: 필터링 효과 측정 방법

### �🛠️ 5. **llm-conversation-filtering-implementation.instructions.md** (663줄 - 🟡 중간)

**역할**: LLM 대화 필터링 구체적 구현 코드  
**참조 시기**: 필터링 시스템 구현, 코드 수정  
**주요 내용**:

- **SmartConversationFilter 클래스**: 핵심 구현 코드
- **다국어 키워드 설정**: JSON 설정 파일 구조
- **LLMManager 통합**: 기존 시스템과의 연동
- **성능 모니터링**: 메트릭 수집 및 최적화

### 🗂️ 6. **integrated-object-storage.instructions.md** (363줄 - 🟢 적정)

**역할**: 통합 객체 저장 패턴 및 데이터 구조  
**참조 시기**: 데이터 통합, 객체 저장, SQLite 작업  
**주요 내용**:

- **통합 객체 구조**: ticket/article 통합 스키마
- **저장 함수**: create/store 패턴
- **SQLite 연동**: 로컬 데이터베이스 관리

---

## 📖 **상세 지침서 (Detailed Guides) - 최적화 완료**

### 🎨 **FDK 개발 패턴** - `fdk-development-patterns.instructions.md` (새로 분할)

**크기**: 적정 (500줄 이하)  
**역할**: Freshdesk FDK 전문 개발 가이드  
**참조 시기**: FDK 앱 개발, JavaScript 구현, iparams 설정  
**주요 내용**:

- **FDK 환경 구성**: Node.js 버전, CLI 설치, 디버깅 명령어
- **company_id 자동 추출**: 도메인 기반 멀티테넌트 식별
- **백엔드 API 연동**: 효율적인 FastAPI 통신 패턴
- **구문 오류 해결**: 중괄호 매칭, FDK 특수 환경 대응

### � **백엔드 구현 패턴** - `backend-implementation-patterns.instructions.md` (새로 분할)

**크기**: 적정 (600줄 이하)  
**역할**: Python FastAPI 백엔드 전문 가이드  
**참조 시기**: 백엔드 API 구현, 비동기 처리, LLM 연동  
**주요 내용**:

- **비동기 프로그래밍**: 동시성 제한, 컨텍스트 매니저, 리소스 관리
- **LLM 최적화**: 캐싱, 배치 처리, 토큰 관리, 스트리밍
- **벡터 검색**: Qdrant 멀티테넌트 격리, 하이브리드 검색
- **플랫폼 추상화**: Freshdesk 중심 확장 가능 설계

### 🚨 **에러 처리 및 디버깅** - `error-handling-debugging.instructions.md` (새로 분할)

**크기**: 적정 (500줄 이하)  
**역할**: 견고한 에러 처리와 디버깅 전문 가이드  
**참조 시기**: 에러 해결, 디버깅, 운영 안정성 개선  
**주요 내용**:

- **재시도 전략**: 지수 백오프, 에러 분류, 회복 메커니즘
- **사용자 친화적 메시지**: 기술적 에러 숨김, 명확한 해결 방안
- **구조화된 로깅**: JSON 형태, company_id 포함, 민감정보 마스킹
- **성능 모니터링**: 실행 시간 추적, 임계값 알림

### 📋 **코딩 원칙 및 체크리스트** - `coding-principles-checklist.instructions.md` (새로 분할)

**크기**: 적정 (500줄 이하)  
**역할**: AI 세션 간 일관성 보장 체크리스트  
**참조 시기**: 모든 코드 작업 시작/완료 시 검증  
**주요 내용**:

- **기존 코드 재활용**: 90% 재사용 원칙, 레거시 로직 보존
- **일관성 체크포인트**: company_id, 플랫폼, 에러 처리, 성능 패턴
- **함정 탐지**: FDK 구문 오류, 캐싱 누락, 메모리 누수 방지
- **표준 워크플로우**: AI 작업 5단계 프로세스

---

## 📖 **레거시 지침서 (분할 전 원본)**

⚠️ **주의**: 아래 지침서들은 크기가 매우 크므로 새로운 분할 지침서를 우선 참조하세요.

### 🛠️ **implementation-guide-legacy.instructions.md** (1,675줄 - 🔴 분할 완료)

**상태**: 백업용 레거시 파일  
**대체**: 위의 4개 분할 지침서로 교체 완료  
**참조**: 긴급 시에만 특정 섹션 참조

### 🔄 **data-workflow.instructions.md** (1,409줄 - 🔴 분할 예정)

**역할**: 데이터 흐름, 저장 구조, DB 설계, 워크플로우  
**참조 시기**: 데이터 처리, DB 스키마 변경, API 설계  
**주요 내용**:

- 전체 데이터 흐름 (Freshdesk → Vector DB → LLM → 응답)
- Qdrant Vector DB 스키마 및 컬렉션 구조
- Freshdesk 전용 플랫폼 지원 (멀티플랫폼 단순화 완료)
- 보안 데이터 처리 및 피드백 루프

### 🏗️ **core-architecture.instructions.md** (1,185줄 - 🔴 분할 예정)

**역할**: 시스템 아키텍처, 성능 최적화, 확장성  
**참조 시기**: 아키텍처 변경, 성능 개선, 시스템 설계  
**주요 내용**:

- **플랫폼별 어댑터 패턴**: 멀티플랫폼 확장 구조
- **API 아키텍처**: 8개 핵심 엔드포인트 설계
- **멀티테넌트 아키텍처**: company_id 기반 격리
- **성능 최적화**: 비동기 처리, 캐싱 전략
- **다국어 키워드 패턴**: 한국어/영어 맞춤 필터링 규칙
- **성능 지표**: 필터링 효율성, 맥락 보존률, 토큰 절약률

### 🔧 5. **llm-conversation-filtering-implementation.instructions.md** ⭐ **NEW**

**역할**: 스마트 대화 필터링 시스템 실제 구현  
**참조 시기**: SmartConversationFilter 클래스 개발/수정  
**주요 내용**:

- **SmartConversationFilter 클래스**: 완전한 구현 가이드
- **다국어 키워드 파일**: multilingual_keywords.json 구조
- **LLMManager 통합**: 기존 시스템과의 통합 방법
- **환경 변수 설정**: 필터링 관련 모든 설정
- **성능 모니터링**: 메트릭 수집 및 품질 관리

---

---

## � **지침서 최적화 현황**

### **📏 크기 분석 (2025.01.20 기준)**

- **총 지침서 크기**: 190.7 KB (8개 파일)
- **🔴 최적화 필요**: 3개 거대 지침서 (implementation-guide, data-workflow, core-architecture)
- **🟢 최적화 완료**: Quick Reference + 특화 지침서들

### **🚀 최적화 효과 (예상)**

- **AI 참조 효율성**: 40-50% 향상
- **컨텍스트 윈도우 사용률**: 60-70% 개선
- **토큰 사용량**: 30-40% 절약

### **📋 다음 최적화 계획 (Phase 2)**

1. 거대 지침서 토픽별 분할
2. 모듈화된 디렉터리 구조 적용
3. 크로스 참조 시스템 구축

---

## 🧠 **AI 참조 가이드라인**

### **⚡ 빠른 참조 전략**

1. **🚀 첫 번째**: `quick-reference.instructions.md`에서 핵심 패턴 확인
2. **📚 두 번째**: `global.instructions.md`에서 공통 원칙 확인
3. **🛠️ 세 번째**: 특화 지침서에서 구체적 구현 확인
4. **📖 최후**: 거대 지침서에서 상세 내용 확인

### **시나리오별 참조 순서**

1. **🚀 모든 개발 작업 시작**:

   - `quick-reference` → `global` → 관련 특화 지침서

2. **🧠 LLM 대화 필터링 개발/수정**:

   - `quick-reference` → `llm-conversation-filtering-strategy` → `llm-conversation-filtering-implementation`

3. **🎨 FDK 프론트엔드 개발**:

   - `quick-reference` → `global` → `implementation-guide` (FDK 섹션)

4. **📊 데이터 처리 변경**:

   - `quick-reference` → `integrated-object-storage` → `data-workflow`

5. **🏗️ 아키텍처 변경/성능 최적화**:
   - `quick-reference` → `global` → `core-architecture`

### **⚠️ AI 참조 시 주의사항**

- **거대 지침서 (🔴)는 필요한 섹션만 참조**
- **Quick Reference로 충분한 경우 거대 지침서 생략**
- **토큰 효율성을 위해 관련 지침서만 선택적 참조**

---

## 📚 **추가 참조 자료**

**문서화 및 분석**:

- **`instructions-optimization-analysis.md`**: 지침서 최적화 분석 보고서
- **기존 작업 문서**: `llm-conversation-filtering-improvement.md`, `smart-filtering-implementation.md`

**레거시 참조용**:

- **기타 instructions.md 파일들**: 구버전 참조용, 필요시에만 간단 참조

---

## 🎯 **결론**

이 지침서 구조는 **AI가 효율적으로 참조**할 수 있도록 **계층적으로 설계**되었습니다:

1. **🚀 Quick Reference**: 모든 작업의 출발점 (500라인 이하)
2. **📚 Core Instructions**: 공통 원칙 (적정 크기)
3. **🛠️ Specialized Instructions**: 특화 기능 (적정 크기)
4. **📖 Detailed Guides**: 상세 구현 (필요시에만 참조)

**새로운 개발 작업 시에는 Quick Reference부터 시작하여 필요에 따라 계층적으로 참조하세요.**

- `data-workflow` → `implementation-guide` (비동기/배치 패턴)

5. **FDK 앱 개발**:

   - `implementation-guide` (FDK 섹션) → `global` (전체 원칙)

6. **에러 해결/디버깅**:
   - `implementation-guide` (디버깅 섹션) → 관련 도메인 지침서

### 중복 방지 원칙

- **전체 원칙은 `global`만**
- **구현 패턴은 `implementation-guide`만**
- **데이터 흐름은 `data-workflow`만**
- **LLM 필터링은 전용 지침서만**
- **레거시는 필요시에만 간단 참조**

---

## 🔄 지침서 업데이트 정책

1. **핵심 5개 지침서 우선**: 새로운 내용은 항상 해당 도메인의 핵심 지침서에 추가
2. **도메인별 분리**: LLM 관련은 LLM 전용 지침서, 일반 구현은 implementation-guide
3. **중복 제거**: 동일 내용이 여러 지침서에 있으면 가장 적절한 곳 1개만 유지
4. **모델 최적화**: 모델이 빠르게 필요한 정보를 찾을 수 있도록 도메인별 구조화

---

## 🧠 **2025년 6월 LLM 대화 필터링 업데이트**

### 📊 **주요 업데이트 내용**

**LLM 대화 필터링 시스템 추가**:

- 기존 5개 대화 제한 → 대화 수 제한 없는 스마트 필터링
- 다국어 지원 (한국어/영어) 키워드 패턴 기반 필터링
- 토큰 예산 관리 및 맥락 보존 우선 알고리즘

**새로운 지침서 구조**:

- `llm-conversation-filtering-strategy.instructions.md`: 전략 및 분석
- `llm-conversation-filtering-implementation.instructions.md`: 실제 구현 가이드
- 기존 `implementation-guide.instructions.md`에 LLM 패턴 추가

### 🏗️ **2024년 12월 모듈화 업데이트**

**LLM 라우터 모듈화**:

- 기존 `llm_router.py` → `core/llm/` 하위 5개 모듈로 분리
- `router.py` (메인 로직), `clients.py` (클라이언트), `models.py` (모델), `utils.py` (유틸리티), `metrics.py` (메트릭)

**데이터 수집 모듈화**:

- 기존 `api/ingest.py` → `core/ingest/` 하위 4개 모듈로 분리
- `processor.py` (핵심 ingest 함수), `validator.py` (검증), `integrator.py` (통합), `storage.py` (저장)

**API 구조 개선**:

- `api/routes/` 하위 엔드포인트들이 `core/` 모듈의 함수들을 import하여 사용
- 비즈니스 로직과 API 엔드포인트 완전 분리

### ✅ **개발 시 주의사항**

- **Import 경로**: `from core.llm import LLMRouter`, `from core.ingest import ingest` 사용
- **모듈 위치**: 핵심 비즈니스 로직은 `core/` 하위에서만 구현
- **API 엔드포인트**: 단순 래퍼 역할만 수행, 복잡한 로직 금지
- **레거시 파일**: 기존 모노리식 파일들은 백업 후 제거 완료

---

**🎯 목표**: 모델이 혼동 없이 "아키텍처/성능", "데이터 처리/워크플로우", "구현 예시"로 명확히 구분된 지침서 세트를 활용하여 효율적인 개발 지원을 제공합니다.
