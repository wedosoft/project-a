# Data Model — 003-ticket-analysis-speed

본 기능은 DB 스키마 변경 없이, **분석 요청/응답 계약과 프론트 상태 모델**을 확장하는 형태로 진행합니다.

## 1) 핵심 엔티티

### AnalyzeRequest
분석 요청(프론트 → 백엔드).

필드(현재 프론트에서 전송 중):
- `ticket_id: string` — Freshdesk ticket id
- `subject: string`
- `description: string`
- `ticket_fields: array` — Freshdesk ticket fields schema(분석/제안용)

추가 고려(확장 가능):
- `include_conversations: boolean` — 기본 true(서버가 수집)

### Conversation (분석 입력용 최소 형태)
Freshdesk conversations를 그대로 전달하지 않고, LLM 입력용으로 축약.

- `created_at: string | null`
- `incoming: boolean | null`
- `private: boolean | null`
- `body_text: string` (길이 상한 적용)

### SummarySection
- `title: string` — 섹션 타이틀(예: "핵심 이슈")
- `content: string` — 섹션 내용(문단/불릿 자유)

검증 규칙:
- 섹션 개수: 2~3개(가능하면 3, 부족하면 2)
- title/content는 빈 문자열 금지

### FieldProposal
- `field_name: string` — Freshdesk API field name
- `field_label: string`
- `proposed_value: any`
- `reason: string`

검증/필터:
- `field_name == "source"` 인 제안은 제거(요구사항)
- `nested_field`의 경우 leaf(3단계) 값 제안이 가능해야 함

### AnalysisResult
- `intent: string` — inquiry/complaint/request/technical_issue
- `sentiment: string` — positive/neutral/negative/urgent
- `summary: string` — (호환성) 1문장 요약
- `summary_sections: SummarySection[]` — (신규) 2~3개 섹션 요약
- `key_entities: string[]`
- `field_proposals: FieldProposal[]`

## 2) 관계/흐름

- `AnalyzeRequest` → Backend에서
  1) Freshdesk conversations 전체 수집(페이지네이션)
  2) ticket_context에 conversations를 포함
  3) LLM 분석 결과를 `AnalysisResult`로 정규화
  4) `field_proposals`에서 `source` 제거

## 3) 프론트 상태(요약)

- `state.selectedSources`: `string[]` 이지만 길이는 항상 0~1
- 분석 결과 렌더링 우선순위:
  1) `summary_sections`가 있으면 섹션 UI로 렌더
  2) 없으면 `summary`를 폴백으로 렌더
