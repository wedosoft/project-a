# 프로젝트 컨텍스트 & 현재 작업

> 이 파일은 **현재 작업 컨텍스트**에만 집중합니다.
> 상세 가이드라인은 `.claude/` 폴더를 참조하세요.

## 🎯 프로젝트 개요
RAG 기반 Freshdesk Custom App - FastAPI + Qdrant + 멀티 LLM

## 🔄 현재 작업 컨텍스트 (2025-07-06)
- **작업**: Query 엔드포인트와 프론트엔드 채팅 UI 연결
- **목표**: 스마트대화/자유대화 기능 완전 구현
- **범위**: 백엔드 API 연결, 실시간 스트리밍, 마크다운 지원
- **상태**: 완료

### 구현된 기능
1. **API 연결**
   - `/query` 엔드포인트 전용 메서드 추가 (`sendChatQuery`)
   - 스트리밍/일반 응답 처리 분리
   - 인증 헤더 자동 설정

2. **채팅 UI 개선**
   - 실제 백엔드 API 호출로 변경
   - 스마트/자유 모드 전환 지원
   - 마크다운 렌더링 추가
   - 실시간 스트리밍 메시지 표시

3. **에러 처리**
   - 네트워크 오류 대응
   - 스트리밍 실패 시 일반 모드 폴백
   - 사용자 친화적 에러 메시지

### 사용 방법
```javascript
// 스마트 모드 (티켓 컨텍스트 기반)
{
  query: "이 티켓의 해결 방법은?",
  agent_mode: true,
  stream_response: true,
  ticket_id: "123"
}

// 자유 모드 (일반 대화)
{
  query: "AI 도구 추천해줘",
  agent_mode: false,
  stream_response: true,
  ticket_id: "123"
}
```

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

## 🛠 개발 환경 가이드
- python을 실행할 때는 반드시 backend/venv 에서 작업하세요. 가상환경이 없으면 만들어서 하세요.