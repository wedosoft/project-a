# Handover: 분석 UI 스트리밍 렌더링 리팩터

> 작성: 2026-03-04 | 상태: **진행 중** | 완료 시 이 문서 삭제

## 목표

`fdk/app/`의 분석 결과 렌더링을 **일괄 innerHTML 교체** → **SSE 스트리밍 단계별 렌더링**으로 개편

---

## 1. 완료된 정리 작업

### 1-1. analyzeBtn 이중 바인딩 해소

- **문제**: `analyzeBtn` 클릭 시 2개 핸들러가 동시 실행, 서로 다른 API 호출
- **수정**: `analysis-ui.js:497-499`에서 `runAnalysis` 바인딩 제거
- **결과**: `app.js`의 `handleAnalyzeTicket()`이 유일한 핸들러

### 1-2. 탭 시스템 단일화

- **문제**: `app.js`는 2탭(`analysis`/`chat`), `analysis-ui.js`는 4탭(`analyze`/`evidence`/`teach`/`history`) — 서로 다른 DOM 대상
- **수정**:
  - `app.js`의 `switchTab()` 함수 삭제
  - `cacheElements()`에서 존재하지 않는 ID(`tabAnalysis`, `tabChat`, `sectionAnalysis`, `sectionChat`) 제거
  - `setupEventListeners()`에서 탭 바인딩 제거
  - 초기화 시 `switchTab('analysis')` → `AnalysisUI.setCurrentTab('analyze')`로 교체
- **결과**: `analysis-ui.js`의 4탭 시스템이 단일 담당

### 1-3. HTML/JS ID 불일치 수정

- **문제**: HTML에 `tabAnalyze` 존재, `app.js`는 `tabAnalysis`를 캐싱 → null
- **수정**: 위 1-2에서 함께 해결 (잘못된 ID 참조 자체를 제거)

### 1-4. retry 버튼 통일

- `analysis-ui.js`의 `showError()` 내 retry 버튼: `runAnalysis()` → `window.handleAnalyzeTicket()`로 변경

---

## 2. 주석 처리된 렌더링 코드 (백업)

`fdk/app/scripts/app.js`에서 `/*__BACKUP_START__` / `__BACKUP_END__*/` 마커로 검색 가능.

| 마커 | 라인 범위 (대략) | 내용 |
|------|-----------------|------|
| `__BACKUP_START__ renderFieldSuggestions` | 795-1095 | 레거시 채팅용 필드 제안 (dead code) |
| `__BACKUP_START__ 분석 렌더링 함수 전체` | 2207-2629 | `renderSolutionSteps`, `renderAnalysisResult`, `renderFieldSuggestionsCard`, `renderAnalysisError` |

---

## 3. 현재 상태

### 동작하는 코드

```
analyzeBtn 클릭
  → handleAnalyzeTicket() (app.js)
    → StreamUtils.streamSolution() — SSE로 백엔드 호출
      → 완료 후 renderAnalysisResult(merged) 호출
        → [STUB] 콘솔 로깅 + "렌더링 리팩터 진행 중..." placeholder
```

### Stub 함수 (app.js 하단, `// [NEW] 스트리밍 렌더링` 섹션)

- `renderAnalysisResult(proposal)` — 데이터 수신 확인용 placeholder
- `renderAnalysisError(message)` — 에러 + 다시 시도 버튼

### 건드리지 않은 코드 (그대로 동작)

- **필드 조작 핸들러**: `window.updateDependentFields`, `window.updateParentFields`, `window.handleLeafSearchApply`, `window.applyEditableFieldUpdates` (app.js:1097-1585)
- **유틸 함수**: `normalizeChoices`, `flattenLeafOptions`, `buildValuePathMap`, `ensureLeafOptions` 등
- **stream-utils.js**: SSE 파싱/전송 로직 전체
- **analysis-ui.js**: 상태 머신, 탭 전환, Dark Mode, Teach 폼, History 탭
- **채팅 기능**: `handleSubmit`, `sendChatStreaming`, `addStreamingMessage` 등

---

## 4. 다음 단계: 스트리밍 렌더링 구현

### 구현 위치

`app.js` 하단의 `// [NEW] 스트리밍 렌더링` 섹션에서 stub 교체

### 핵심 변경 포인트

1. **`handleAnalyzeTicket()`** (app.js:2133) — SSE `onProgress` 콜백에서 단계별 렌더링 호출
   - 현재: 완료 후 `renderAnalysisResult(merged)` 일괄 호출
   - 변경: 각 SSE 이벤트(`searching`, `analyzing`, `field_proposal`, `complete` 등)마다 점진적 렌더링

2. **`renderAnalysisResult(proposal)`** — 일괄 innerHTML → 점진적 append
   - 요약 카드 → 원인 카드 → 해결책 카드 → 필드 제안 카드 순서로 SSE 수신 시 하나씩 추가

3. **`renderFieldSuggestionsCard(proposal)`** — 필드 제안 카드 별도 렌더링
   - 백업에서 로직 참고 (nested_field 처리, choices 연쇄 등)
   - 인라인 이벤트에서 `window.updateDependentFields` 등 기존 핸들러 호출 유지

### SSE 이벤트 타입 참고 (stream-utils.js 기준)

| 이벤트 | 의미 | 렌더링 동작 |
|--------|------|-------------|
| `started` | 요청 시작 | 스켈레톤/로딩 표시 |
| `searching` | 유사 사례 검색 중 | 티커 갱신 |
| `search_result` | 검색 완료 | 티커 갱신 |
| `analyzing` | AI 분석 중 | 티커 갱신 |
| `field_proposal` | 필드 제안 생성 중 | 티커 갱신 |
| `draft_response` | 응답 생성 중 | 부분 렌더링 가능 |
| `complete` | 최종 결과 | 전체 렌더링 완성 |
| `error` | 오류 | `renderAnalysisError()` |

### 주의 사항

- 필드 조작 핸들러(`window.updateDependentFields` 등)는 렌더링된 HTML의 인라인 이벤트에서 직접 호출됨 → **같은 ID 패턴과 data-attribute 유지 필수**
  - ID 패턴: `input-{fieldName}-{messageId}-{level}`, `leafsearch-{fieldName}-{messageId}`, `leafhidden-{fieldName}-{messageId}`
  - data 속성: `data-field-name`, `data-level`
- `analysis-ui.js`의 빈 렌더 함수(`renderStreamField`, `renderGateAndMeta` 등)는 V2 API(`/api/tickets/{id}/analyze/stream`) 전용 — 현재 사용하지 않지만 향후 통합 시 참고

---

## 5. 파일 구조 요약

```
fdk/app/
├── index.html              # 4탭 UI (Analyze/Evidence/Teach/History)
└── scripts/
    ├── backend-config.js   # window.BACKEND_CONFIG (변경 없음)
    ├── stream-utils.js     # window.StreamUtils - SSE 유틸 (변경 없음)
    ├── analysis-ui.js      # 상태 머신, 탭 전환, Dark Mode (바인딩만 수정)
    └── app.js              # 메인 앱 — 렌더링 stub 상태
        ├── Store (1-167)
        ├── API (169-242)
        ├── UI & Utils (264-789)
        ├── [BACKUP] renderFieldSuggestions (795-1095)
        ├── Global Window Handlers (1097-1585) — 유지
        ├── Main / Init (1589-1683)
        ├── Event Handlers (1685-2205)
        ├── [BACKUP] 렌더링 함수 전체 (2207-2629)
        └── [NEW] 스트리밍 렌더링 stub (2631~)
```
