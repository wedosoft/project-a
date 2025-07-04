# 프로젝트 컨텍스트 & 현재 작업

> 이 파일은 **현재 작업 컨텍스트**에만 집중합니다.
> 상세 가이드라인은 `.claude/` 폴더를 참조하세요.

## 🎯 프로젝트 개요
RAG 기반 Freshdesk Custom App - FastAPI + Qdrant + 멀티 LLM

## 🔄 현재 작업 컨텍스트 (2025-07-04)
- **작업**: Claude 지침 구조 최적화
- **목표**: 지침 관리 간소화 및 일관성 확보
- **범위**: 전체 프로젝트 문서 구조
- **상태**: 진행 중

## 📂 상세 지침 위치
- **전역 원칙**: `~/.claude/CLAUDE.md` (코딩 스타일, 보안 등)
- **백엔드 전체**: `.claude/backend-guide.md` (아키텍처, 패턴)
- **프론트엔드**: `.claude/frontend-guide.md` (FDK, UI 컴포넌트)
- **데이터베이스**: `.claude/modules/database.md` (Qdrant, 쿼리 최적화)
- **LLM 관리**: `.claude/modules/llm.md` (다중 제공자, 캐싱)
- **검색 엔진**: `.claude/modules/search.md` (벡터 검색, 필터링)
- **데이터 수집**: `.claude/modules/ingest.md` (배치 처리, OCR)

## ⚡ 빠른 참조
```bash
# 지침 관리 도구
./scripts/claude-guide-manager.sh

# 구조 확인
./scripts/claude-guide-manager.sh structure

# 현재 컨텍스트 확인
./scripts/claude-guide-manager.sh context

# 워크트리 동기화 (중요!)
./scripts/claude-guide-manager.sh sync

# 워크트리 상태 확인
./scripts/claude-guide-manager.sh status
```

## 🌳 워크트리 지침 관리
- **자동 동기화**: 지침 변경 시 `sync` 명령으로 모든 워크트리에 반영
- **상태 확인**: `status` 명령으로 워크트리별 동기화 상태 확인
- **일관성 유지**: 모든 워크트리에서 동일한 지침 적용

## 🎯 Claude Code 사용 시나리오

### 📝 작업 시작 시
```
"현재 CLAUDE.md 컨텍스트를 확인하고, 필요하면 .claude/backend-guide.md도 참조해주세요"
```

### 🔧 특정 모듈 작업 시
```
"데이터베이스 최적화 작업입니다. .claude/modules/database.md 가이드라인을 따라주세요"
"LLM 통합 작업입니다. .claude/modules/llm.md 패턴을 적용해주세요"
"검색 성능 개선입니다. .claude/modules/search.md 최적화 기법을 사용해주세요"
```

### ⚡ 성능 최적화 시
```
"성능 최적화 작업입니다. .claude/backend-guide.md의 성능 섹션과 해당 모듈 가이드를 모두 참조해주세요"
```

### 🐛 디버깅 시
```
"디버깅 중입니다. .claude/backend-guide.md의 로깅 패턴과 에러 처리 방식을 따라주세요"
```

---
**💡 팁**: Claude Code 사용 시 이 파일을 먼저 읽고, 필요에 따라 `.claude/` 폴더의 상세 가이드를 참조하세요.

## 📚 관련 문서
- **📖 관리 도구 가이드**: `docs/claude-guide-manager-guide.md`
- **🔧 스크립트 파일**: `scripts/claude-guide-manager.sh`
- **🌍 글로벌 지침**: `~/.claude/CLAUDE.md`
