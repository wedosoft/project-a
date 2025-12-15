# Quickstart — 003-ticket-analysis-speed

이 문서는 기능 개발/검증을 위한 최소 실행 절차입니다.

## 로컬 실행 구성

- Frontend: `project-a/frontend` (Freshdesk FDK Custom App, Node 18 필요)
- Backend: `agent-platform` (FastAPI, Python >= 3.9)

## Backend 실행 (agent-platform)

- 환경변수: `agent-platform/.env.local` 사용(이미 repo에 존재)
- 실행: uvicorn으로 API 서버 기동
  - 엔드포인트: `/api/assist/analyze`, `/api/assist/analyze/stream`

## Frontend 실행 (project-a/frontend)

- FDK local 실행 환경에서 `index.html`을 ticket_top_navigation에 로드
- `frontend/config/requests.json`의 `backendApiPost/backendApi` host가 현재 백엔드 주소(ngrok/로컬)로 맞는지 확인

## 수동 검증 체크리스트(수용 기준)

- AC1) 채팅 소스는 항상 1개만 선택됨(새 선택 시 이전 선택 해제)
- AC2) 대화 50개 이상 티켓에서 분석 결과가 대화 전체를 반영(서버 로그/결과 품질로 확인)
- AC3) 분석 결과가 2~3개 섹션 타이틀로 표시됨
- AC4) `source`는 제안 카드에도 없고 업데이트 payload에도 없음
- AC5) 필드 적용 시 숫자 필드(`priority/status/...`)가 `NaN`이 되지 않음

## 관찰 포인트(성능)

- 동일 티켓을 연속으로 분석할 때, conversations 재요청이 줄어드는지(캐시 동작) 확인
- Freshdesk API rate-limit(429) 발생 시 graceful handling 여부 확인
