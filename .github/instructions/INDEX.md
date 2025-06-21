# 📚 Instructions Directory Index

## 🎯 Quick Start Guide

### 🚀 AI/모델이 먼저 참조해야 할 파일들 (우선순위 순)
1. **[Quick Reference](./core/quick-reference.instructions.md)** - 핵심 패턴과 체크리스트
2. **[Global Instructions](./core/global.instructions.md)** - 전역 규칙과 원칙
3. **[README](./core/README.md)** - 상세 가이드라인과 구조 설명

### 📂 디렉터리 구조 및 참조 가이드

## 🏗️ Core (핵심 참조)
**모든 작업 전 필수 참조**
- `global.instructions.md` - 전역 개발 원칙과 규칙
- `quick-reference.instructions.md` - 핵심 패턴 요약
- `README.md` - 전체 지침서 구조와 상세 가이드

## 💻 Development (개발 패턴)
**개발 작업 시 참조**
- `fdk-development-patterns.instructions.md` - FDK 개발 패턴
- `backend-implementation-patterns.instructions.md` - 백엔드 구현 패턴
- `error-handling-debugging.instructions.md` - 오류 처리 및 디버깅
- `coding-principles-checklist.instructions.md` - 코딩 원칙 체크리스트
- `api-architecture-file-structure.instructions.md` - API 구조 가이드

## 📊 Data (데이터 처리)
**데이터 관련 작업 시 참조**
- `data-workflow.instructions.md` - 전체 데이터 워크플로우
- `data-collection-patterns.instructions.md` - 데이터 수집 패턴
- `data-processing-llm.instructions.md` - LLM 데이터 처리
- `vector-storage-core.instructions.md` - 벡터 저장소 핵심 패턴 ⭐
- `vector-search-advanced.instructions.md` - 고급 벡터 검색 기능
- `storage-abstraction-core.instructions.md` - 스토리지 추상화 핵심 패턴 ⭐

## 🎯 Specialized (특화 기능)
**특정 기능 구현 시 참조**
- `llm-conversation-filtering-strategy.instructions.md` - LLM 대화 필터링 전략
- `llm-conversation-filtering-implementation.instructions.md` - LLM 대화 필터링 구현
- `integrated-object-storage.instructions.md` - 통합 객체 저장소
- `platform-adapters-multiplatform.instructions.md` - 멀티플랫폼 어댑터
- `monitoring-testing-strategy.instructions.md` - 모니터링 및 테스팅
- `scalability-roadmap-implementation.instructions.md` - 확장성 로드맵

---

## 🎯 AI 참조 가이드라인

### 📋 작업별 참조 순서

#### 🚀 새 기능 개발
1. `core/quick-reference.instructions.md` (핵심 패턴 확인)
2. `development/` 관련 패턴 파일
3. `data/` 또는 `specialized/` 해당 기능 파일

#### 🐛 디버깅 및 오류 수정
1. `development/error-handling-debugging.instructions.md`
2. `core/quick-reference.instructions.md`
3. 해당 기능 영역 파일

#### 📊 데이터 처리 작업
1. `data/data-workflow.instructions.md` (전체 흐름 파악)
2. 구체적 작업에 맞는 data/ 하위 파일
3. `core/quick-reference.instructions.md`

#### 🎯 특화 기능 구현
1. `specialized/` 해당 기능 파일
2. `development/` 관련 구현 패턴
3. `core/quick-reference.instructions.md`

### ⚡ 효율적 참조 원칙
- **Always Start**: `core/quick-reference.instructions.md`
- **Domain Specific**: 해당 영역 디렉터리의 메인 파일
- **Cross Reference**: 관련 링크와 "See Also" 섹션 활용
- **Legacy Avoid**: legacy/ 파일들은 참고용으로만 사용

### 📊 파일 크기 가이드
- **Quick Reference**: ~8KB (핵심 요약)
- **Development**: 15-25KB (구현 패턴)
- **Data**: 15-30KB (워크플로우 포함)
- **Specialized**: 20-35KB (특화 기능)

---

## 🔄 업데이트 및 관리

### 📅 정기 점검 항목
- [ ] 각 디렉터리별 파일 수 (5-8개 이하 권장)
- [ ] 크로스 링크 및 참조 정확성
- [ ] Quick Reference 최신성
- [ ] Legacy 파일 정리

### 🎯 최적화 목표
- **참조 효율성**: 3단계 이하 탐색으로 필요 정보 접근
- **관리 용이성**: 카테고리별 명확한 분리
- **크기 최적화**: 개별 파일 40KB 이하 유지
- **크로스 링크**: 관련 지침서 간 연결성 강화

---

## 🎉 최신 업데이트 (2025년 6월 21일)

### ✅ Backend Core 리팩토링 완료
**대규모 구조 개선이 완료되었습니다!**

#### 🏗️ 새로운 백엔드 구조
```
backend/core/
├── database/          # 벡터DB, SQLite 관리
├── data/              # Pydantic 모델, 스키마
├── search/            # 하이브리드 검색, GPU 임베딩
├── processing/        # 데이터 처리 파이프라인
├── llm/              # 통합 LLM 관리 (완전 통합)
├── platforms/        # Freshdesk 등 플랫폼 어댑터
├── ingest/           # 데이터 수집
└── legacy/           # 레거시 코드 보관
```

#### 🚀 주요 개선사항
- **모듈화 완료**: 33개 산재 파일 → 8개 체계적 모듈
- **LLM 통합**: 분산된 LLM 관리 코드 완전 통합
- **GPU 임베딩**: torch, sentence-transformers 설치 완료
- **Pydantic v2**: 완전 호환 (`@model_validator` 적용)
- **플랫폼 통합**: Freshdesk → `core/platforms/freshdesk/`

#### 📋 참조할 문서
- **[Backend Refactoring Report](../backend/docs/BACKEND_REFACTORING_COMPLETION_REPORT.md)** - 완료 보고서
- **[System Architecture](./core/system-architecture.instructions.md)** - 업데이트된 구조 가이드
