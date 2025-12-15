# Research (Phase 0) — 003-ticket-analysis-speed

이 문서는 `spec.md`의 미확정/리스크 항목을 조사하고, 구현 방향을 결정한 근거를 기록합니다.

## Decision 1) 분석에 **전체 대화(conversations)** 를 포함한다

### Decision
- Backend(`agent-platform`)에서 Freshdesk Conversations API를 `per_page=30`으로 **페이지네이션 루프**를 돌려 **모든 대화**를 수집한 뒤, LLM 분석 입력(`ticket_context`)에 포함한다.
- 수집한 conversations는 토큰 폭증을 막기 위해 **필요 필드만 축약**하고, 각 메시지 본문은 **상한 길이로 절단**(예: 2,000자)한다.

### Rationale
- Freshdesk는 conversations API가 페이지당 최대 30개로 제한되어, 50개 이상 티켓은 기본 조회만으로는 맥락 손실이 발생한다.
- 프론트는 현재 분석 요청 payload에 conversations를 포함하지 않기 때문에(현재 `ticket_id/subject/description/ticket_fields`), 서버 측 수집이 가장 자연스럽다.

### Alternatives considered
- **A. 프론트에서 conversations를 전송**: payload가 커지고, SSE/프록시 제한과 토큰 비용 증가 위험이 있어 보류.
- **B. 30개만 분석**: 수용 기준(AC2)을 만족하지 못함.
- **C. 마지막 30개만 분석**: 원인/히스토리가 초기 대화에 있는 경우 놓칠 수 있어 보류.

## Decision 2) 요약 출력 포맷을 2~3개 섹션으로 변경한다

### Decision
- LLM 출력에 `summary_sections`(2~3개 섹션) 구조를 추가한다.
  - 예: `[{"title":"핵심 이슈","content":"..."}, ...]`
- 기존 `summary`(1문장)는 **호환성 유지**를 위해 남기되, UI는 `summary_sections`가 있으면 이를 우선 렌더링한다.

### Rationale
- 상담원이 빠르게 판단할 수 있도록 “섹션 타이틀 기반 요약”이 목표이며, 1문장 요약은 정보 밀도가 낮다.

### Alternatives considered
- **A. LLM은 1문장 요약 유지 + 프론트에서 임의로 섹션 분해**: 신뢰도 낮고 규칙이 복잡해짐.

## Decision 3) `source` 필드는 제안/적용에서 제외한다

### Decision
- Backend: 분석 결과의 `field_proposals`에서 `field_name == "source"`는 필터링.
- Frontend: 렌더링 및 업데이트 payload 생성 단계 모두에서 `source`를 무시.

### Rationale
- 사용자 요구사항(AC4)이며, `source`는 Freshdesk 표준 숫자 필드로 타입/매핑 오류에 취약함.

### Alternatives considered
- **A. `source`를 유지하고 숫자/라벨 매핑 강화**: 사용자가 원치 않으며, 실패 비용이 큼.

## Decision 4) 채팅 소스 선택은 단일 선택으로 제한한다

### Decision
- UI는 멀티 선택 형태를 유지해도 되지만, 상태(`selectedSources`)는 항상 길이 0~1을 유지하도록 강제한다.

### Rationale
- 요구사항(AC1). UX 측면에서도 “질문당 하나의 근거 소스”가 더 예측 가능.

### Alternatives considered
- **A. 체크박스 → 라디오 버튼 전환**: UI 변경 폭이 커질 수 있어 단계적으로 진행.

## Decision 5) 체감 성능: 불필요한 호출을 줄이고 캐시를 추가한다

### Decision
- Backend에서 분석 입력은 **요청 payload의 subject/description을 신뢰**하여(이미 프론트가 티켓을 읽어온 상태), 추가 티켓 조회를 최소화하고 **conversations만 보완 수집**한다.
- 동일 티켓에 대해 반복 분석이 발생하는 경우를 위해, `ticket_id` 기준의 **짧은 TTL 캐시(예: 30~60초)** 로 conversations 재요청을 줄인다(메모리 캐시).

### Rationale
- Freshdesk API 호출이 지연의 가장 큰 요인이 될 가능성이 높고, 같은 화면에서 “분석 재시도”가 잦다.

### Alternatives considered
- **A. Supabase/DB에 conversations 저장**: 운영 부담이 커지고 PII/보안 이슈가 증가.
- **B. 캐시 없이 매번 풀 스캔**: 체감 지연이 반복.
