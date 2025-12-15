#+#+#+#+---------------------------------------------------------------------
# Implementation Plan: 003-ticket-analysis-speed

**Branch**: `003-ticket-analysis-speed` | **Date**: 2025-12-15 | **Spec**: `/Users/alan/GitHub/project-a/specs/003-ticket-analysis-speed/spec.md`
**Input**: Feature specification from `specs/003-ticket-analysis-speed/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

이 기능은 **(1) 티켓 분석 품질/속도 개선**과 **(2) 필드 제안 UX 정리**를 동시에 다룹니다.

- UX는 기존대로 **탭 2개(분석/채팅) 유지**, 채팅은 유지하되 **소스 선택은 단일 선택만 허용**합니다.
- 분석은 상담원이 바로 판단할 수 있도록 **2~3개 섹션 타이틀 기반 요약** + **필드 제안 카드**를 제공합니다.
- 분석 데이터 완전성을 위해 Freshdesk conversations는 **per_page=30 페이지네이션으로 전체 수집**합니다.
- 필드 업데이트 제안/적용에서 `source` 필드는 제외합니다.

상세 결정/근거는 `research.md`를 따릅니다.

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process.
-->

**Language/Version**: Frontend(Vanilla JS/HTML + Freshdesk FDK, Node 18.20.8) / Backend(Python >= 3.9)

**Primary Dependencies**: Frontend(FDK runtime + request templates) / Backend(FastAPI, httpx, langgraph/langchain, openai client, Supabase)

**Storage**: Supabase(기존 캐시) / 본 기능은 DB 변경 없이 응답 스키마 확장 중심

**Testing**: Backend(pytest) / Frontend(수동 검증 중심, 필요 시 tasks에서 테스트 추가)

**Target Platform**: Frontend(Freshdesk Ticket UI / FDK iframe) + Backend(Linux 서버/Fly 또는 로컬 ngrok)

**Project Type**: Web app (FDK frontend + FastAPI backend)

**Performance Goals**:
- 상담원 체감 기준으로 분석 결과가 더 빨리 표시되도록 개선(특히 반복 분석/재시도 시)

**Constraints**:
- Freshdesk Conversations API는 페이지당 30개 제한
- FDK 프록시/네트워크 환경에서 타임아웃이 발생할 수 있으므로, 서버 호출 수와 페이로드 크기를 최소화

**Scale/Scope**:
- 단일 티켓의 대화가 50개 이상인 케이스를 정상 지원

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- `project-a/.specify/memory/constitution.md`는 현재 **placeholder 템플릿**이며, 강제 게이트가 정의되어 있지 않습니다.
- 따라서 본 계획은 추가 게이트 없이 진행합니다.
- (권장) 추후 constitution을 확정해 “테스트/품질/배포” 게이트를 명문화합니다.

## Project Structure

### Documentation (this feature)

```text
specs/003-ticket-analysis-speed/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
frontend/
├── app/
│   ├── index.html
│   └── scripts/
│       ├── app.js
│       └── stream-utils.js
└── config/
  └── requests.json
```

### Source Code (workspace: external dependency)

이 기능은 **두 개의 repo**에 걸쳐 변경이 발생합니다.

```text
agent-platform/
└── app/
    ├── api/routes/assist.py         # /assist/analyze, /assist/analyze/stream
    ├── services/
    │   ├── freshdesk_client.py      # get_all_conversations(이미 구현)
    │   └── llm_adapter.py           # summary_sections 출력 + source 제안 제거
    └── agents/
        └── analyzer.py              # field_proposals 필터링(예: source 제거)
```

**Structure Decision**: Web app(프론트 FDK + 백엔드 FastAPI)이며, 프론트는 `project-a/frontend`, 백엔드는 `agent-platform`이 소스 오브 트루스입니다.

## Execution Strategy (High-level)

1) **Frontend (UX)**
- 채팅 소스 선택 단일화(상태 0~1 유지)
- 분석 결과 렌더링을 `summary_sections` 우선으로 구성
- 필드 제안/적용에서 `source` 완전 제거(렌더/업데이트 모두)

2) **Backend (completeness + speed)**
- 분석 시작 시 Freshdesk conversations를 전체 수집(페이지네이션)
- LLM 입력에는 conversations를 축약 형태로 포함(토큰 폭증 방지)
- `summary_sections`를 포함하도록 LLM 프롬프트/후처리 업데이트
- `source` 필드 제안 필터링
- 동일 티켓 반복 분석 시를 위한 짧은 TTL conversations 캐시(메모리)

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

해당 없음(현재 constitution 게이트가 정의되어 있지 않으며, 본 계획은 추가 복잡도 도입 없이 진행).
