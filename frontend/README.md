# CopilotKit Freshdesk 통합 POC

이 프로젝트는 Freshdesk 티켓 응답 작성 시 AI 자동 텍스트 생성을 지원하는 CopilotKit 통합 개념 증명(POC)입니다.

## 📋 기능

- AI 지원 텍스트 입력 영역
- 티켓 컨텍스트 기반 자동 응답 제안
- Freshdesk 모달 형태로 통합

## 🚀 시작하기

### 사전 요구 사항

- Node.js 18.18.2
- npm 또는 yarn
- FDK(Freshworks Developer Kit)

### 설치 방법

1. 저장소 복제:
   ```
   git clone [저장소 URL]
   ```

2. 프로젝트 디렉토리로 이동:
   ```
   cd frontend
   ```

3. 빌드 스크립트 실행:
   ```
   ./build.sh
   ```

4. 로컬에서 앱 실행:
   ```
   fdk run
   ```

## ⚙️ 설정 방법

1. CopilotKit API 키 설정:
   - `config/iparams.json`에 API 키 설정이 정의되어 있음
   - 앱 설치 시 CopilotKit에서 발급받은 API 키 입력

## 🔧 구조

- `app/scripts/components/copilot-textarea.jsx`: CopilotKit React 컴포넌트
- `app/scripts/copilot-app.js`: React 앱 진입점
- `app/copilot-modal.html`: CopilotKit 기능이 포함된 모달 템플릿

## 📝 사용 방법

1. Freshdesk 티켓 페이지에서 앱 아이콘 클릭
2. 또는 사이드바에서 "AI 응답 작성" 버튼 클릭
3. 모달 창에서 AI의 제안을 확인하고 필요에 따라 수정
4. "응답하기" 버튼을 클릭하여 응답 제출

## 🔮 향후 개선 방향

1. 실제 티켓 응답 API와 통합
2. 티켓 세부 정보 추가 활용
3. 응답 템플릿 다양화
4. UI/UX 개선

## 📄 라이센스

회사 내부용
