# 📚 AI Instructions Directory Index

> **🚨 AI 필수 준수사항**: 모든 작업은 **"제안 > 컨펌 > 단계적 작업"** 3단계 프로세스 준수 필요

> **🚀 AI 첫 참조 가이드**: 이 파일 → `../docs/MASTER_STATUS.md` → `core/quick-reference.instructions.md` → 작업별 지침서

## 🚨 **AI 작업 프로세스 (절대 준수)**
1. **📋 제안**: 변경사항 상세 설명 및 영향도 분석
2. **✅ 컨펌**: 사용자 승인 대기 (필수)
3. **🔧 실행**: 컨펌 후에만 단계적 작업 진행

## 🎯 즉시 참조 (우선순위 순)

### 🔥 필수 시작점 (2025-06-28 최신화)
1. **[Master Status](../docs/MASTER_STATUS.md)** 🆕 - 프로젝트 마스터 현황 (⭐ 순차 실행 아키텍처 적용 완료)
2. **[Current Issues](../docs/CURRENT_ISSUES.md)** 🆕 - 현재 해결 중인 이슈들 (6개 주요 이슈 해결)
3. **[Project Roadmap](../docs/ROADMAP.md)** 🆕 - 프로젝트 로드맵 (Phase 2 시작)
4. **[Quick Reference](./core/quick-reference.instructions.md)** ⭐ - 핵심 패턴 (5분 읽기)
5. **[Global Instructions](./core/global.instructions.md)** - 전역 규칙과 원칙

### 🎯 주요 아키텍처 변경사항 (2025-06-28)
- **⭐ 순차 실행 패턴**: 병렬 처리(InitParallelChain) 제거, 3~4초 성능 달성
- **⭐ doc_type 제거**: 코드 레벨 필터링 완전 제거, Qdrant 쿼리 레벨만 사용
- **⭐ 실시간 요약 분리**: Freshdesk API에서만 실시간 요약, 벡터 검색과 분리
- **⭐ End-to-End 테스트**: 실제 데이터로 전체 파이프라인 검증 완료

### 📈 핵심 지침서만 유지 (간소화 완료)

## 🏗️ Core - 필수 참조 파일들 (7개 핵심 지침서)
| 파일 | 용도 | 참조 시점 |
|------|------|-----------|
| **[Quick Reference](./core/quick-reference.instructions.md)** | 핵심 패턴 요약 | 모든 작업 시작 |
| **[Global Instructions](./core/global.instructions.md)** | 전역 개발 원칙 | 새 기능 개발 시 |
| **[Core Architecture](./core/core-architecture.instructions.md)** | 핵심 아키텍처 | 시스템 설계 시 |
| **[System Architecture](./core/system-architecture.instructions.md)** | 전체 시스템 구조 | 아키텍처 변경 시 |
| **[Multitenant Security](./core/multitenant-security.instructions.md)** | 보안 패턴 | 보안 관련 작업 |
| **[Performance Optimization](./core/performance-optimization.instructions.md)** | 성능 최적화 | 성능 개선 시 |

## 💻 Development - 개발 패턴 가이드 (5개 핵심 패턴)
| 주요 파일 | 설명 |
|-----------|------|
| `error-handling-debugging.instructions.md` | 디버깅 및 오류 처리 |
| `backend-implementation-patterns.instructions.md` | FastAPI 백엔드 패턴 |
| `fdk-development-patterns.instructions.md` | FDK 프론트엔드 개발 |
| `coding-principles-checklist.instructions.md` | 코딩 원칙 체크리스트 |
| `api-architecture-file-structure.instructions.md` | API 아키텍처 및 파일 구조 |

---

## 📋 AI 참조 가이드라인

### 🚀 간소화된 참조 경로 (1-2단계만)

#### 새 기능 개발
1. `../docs/MASTER_STATUS.md` (30초) → 현재 상황 파악
2. `core/quick-reference.instructions.md` (5분) → 핵심 패턴

#### 문제 해결
1. `../docs/CURRENT_ISSUES.md` (1분) → 알려진 이슈 확인
2. `development/error-handling-debugging.instructions.md` (필요시)

#### 프로젝트 계획
1. `../docs/ROADMAP.md` (3분) → 전체 방향성 파악

### ⚡ 핵심 원칙
- **Always Start**: Master Status부터 시작
- **Keep Simple**: 1-2단계 참조로 제한
- **Current First**: 최신 정보 우선

---

## 🗂️ 아카이브 완료 (2025-06-27)

### ✅ 대폭 정리 완료
- **docs 폴더**: 45개 → 10개 핵심 문서
- **지침서 참조**: 복잡한 3-4단계 → 간단한 1-2단계
- **구버전 제거**: 2025-06-22, 06-23 날짜 정보들 아카이브

---

## �️ 아카이브 완료 (2025-01-20)

### ✅ 대폭 정리 완료
- **지침서 구조**: 복잡한 참조 체계 → 핵심 12개 지침서만 유지
- **core 폴더**: 7개 핵심 아키텍처 지침서
- **development 폴더**: 5개 핵심 개발 패턴
- **구버전 제거**: session-summary, status 파일들 아카이브

### � 아카이브 위치
- **지침서**: `../archived_instructions/` (core_legacy, development_legacy)
- **문서**: `../archived_docs/` (40개+ 파일)
- **태스크**: `../archived_tasks/` (task_001.txt ~ task_030.txt)

---

> 💡 **완전 간소화 완료**: 이제 AI는 12개 핵심 지침서만 참조하면 
> 모든 개발 작업을 수행할 수 있습니다!

---

**📚 이 인덱스는 AI와 개발자의 효율적인 작업을 위해 지속적으로 최적화됩니다.**
