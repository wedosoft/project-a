# Tasks: 003-ticket-analysis-speed

> 체크박스는 구현 진행 상황을 나타냅니다. 완료한 항목은 반드시 `[X]`로 갱신합니다.

## Phase 0 — Setup

- [X] (S1) 리포지토리 상태/브랜치 확인 및 작업 범위 고정
- [X] (S2) ignore 파일 점검 (.gitignore/.dockerignore 등, 필요 시 최소 패턴만 추가)

## Phase 1 — Tests (Backend)

- [X] (T1) `agent-platform`에 유닛 테스트 추가: `source` 제안 필터링
- [X] (T2) `agent-platform`에 유닛 테스트 추가: assist 분석 시 conversations 포함(클라이언트 호출을 mock)

## Phase 2 — Core Implementation

### Backend (agent-platform)

- [X] (B1) `/assist/analyze`에서 Freshdesk conversations 전체 페이지네이션 수집하여 `ticket_context.conversations`에 포함
- [X] (B2) `/assist/analyze/stream`에서도 동일하게 conversations 수집/포함
- [X] (B3) conversations 메모리 TTL 캐시 추가(tenant_id+ticket_id 키)로 반복 호출 비용 절감
- [X] (B4) `LLMAdapter.analyze_ticket()` 결과에 `summary_sections`(2~3개 섹션) 포함 (기존 `summary`는 하위 호환 유지)
- [X] (B5) `Analyzer` 단계에서 `field_proposals`에서 `source` 제거(추가 안전장치)

### Frontend (project-a/frontend)

- [X] (F1) 채팅 소스 선택 UI를 단일 선택으로 강제(선택 변경 시 기존 선택 해제)
- [X] (F2) 분석 결과 렌더링을 `summary_sections` 우선으로 표시(2~3 섹션 타이틀)
- [X] (F3) 필드 제안 카드/업데이트 payload에서 `source` 완전 제거

## Phase 3 — Integration & Validation

- [ ] (I1) `requests.json`/헤더 흐름 확인(backend 호출 시 Freshdesk domain/api key 전달)
- [ ] (I2) 로컬 백엔드 + FDK 앱에서 분석/필드적용 smoke test (대화 30개 초과 티켓 포함)

## Phase 4 — Polish

- [ ] (P1) `pytest -q` 통과 확인(backend)
- [ ] (P2) 로그/에러 메시지 정리(사용자에게 의미 있는 실패 메시지)
