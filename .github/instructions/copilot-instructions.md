---
applyTo: "**"
---

# GitHub Copilot 프로젝트별 지침 - Freshdesk Custom App (project-a)

## 🚨 중요: 글로벌 지침 준수 필수

**모든 파일 생성/수정 작업은 반드시 다음 절차를 따라야 합니다:**

1. **제안 단계**: 어떤 파일을 생성하거나 수정할지 구체적으로 제안
2. **사용자 컨펌 대기**: "진행해도 될까요?" 형태로 명시적 승인 요청
3. **승인 후 실행**: 사용자가 "네", "진행해주세요" 등으로 승인한 후에만 파일 작업 진행

**절대 금지사항:**

- 제안 없이 바로 파일 생성/수정
- 사용자 승인 없이 `create_file`, `insert_edit_into_file`, `replace_string_in_file` 도구 사용
- "일단 만들어보고 확인해보세요" 스타일의 접근

## 📋 프로젝트 개요

- **프로젝트명**: Freshdesk Custom App (Prompt Canvas)
- **목적**: RAG 기반 AI 상담사 지원 시스템
- **백엔드**: Python 3.10, FastAPI, Qdrant, LLM Router
- **프론트엔드**: Freshdesk FDK, BlockNote 에디터
- **특징**: 멀티테넌트, 동적 Freshdesk 연동

## 🔧 기술 스택별 지침

### Freshdesk FDK 개발

- Node.js v14.x ~ v18.x 환경 유지
- FDK 검증 실패 시 단계별 디버깅 (구문 검사 → 브라우저 콘솔 → 파일별 검증)
- 보안: API 키 하드코딩 절대 금지, iparams 기본값은 빈 문자열
- 동적 Freshdesk 설정: 헤더를 통한 도메인/API 키 전달

### Python 백엔드 개발

- 타입 힌트 필수, 한글 주석 필수
- 비동기 처리 (async/await) 적극 활용
- company_id 기반 멀티테넌트 데이터 분리
- LLM Router 패턴으로 다중 LLM 제공자 지원

### VS Code 디버깅 환경

- FDK 개발 서버는 NODE_ENV=development로 실행
- 소스맵 생성을 위한 개발 모드 필수
- launch.json의 sourceMapPathOverrides 설정 중요
- 중단점 활성화를 위한 FDK 서버 상태 확인

## 🚀 GitHub Copilot 최적화 설정

### 코드 생성 지침

- 모든 함수에 한글 독스트링 작성
- Python: 타입 힌트 + async/await 패턴
- JavaScript: ES6+ 문법 + FDK API 활용
- 에러 처리 및 로깅 코드 자동 포함

### 프로젝트 특화 패턴

```python
# Python 백엔드 패턴
async def process_freshdesk_data(ticket_id: str, company_id: str) -> Dict[str, Any]:
    """Freshdesk 티켓 데이터를 처리하고 벡터 임베딩을 생성합니다."""
    try:
        # company_id 필터를 적용한 안전한 데이터 처리
        pass
    except Exception as e:
        logger.error(f"티켓 처리 실패: {e}")
        raise
```

```javascript
// JavaScript FDK 패턴
async function getFreshdeskConfig() {
  try {
    // FDK API를 통한 동적 설정 추출
    const context = await window.parent.app.instance.context();
    return {
      domain: context.account.domain,
      apiKey: await window.parent.app.iparams.get("freshdesk_api_key"),
    };
  } catch (error) {
    console.error("Freshdesk 설정 추출 실패:", error);
    throw new Error("Freshdesk 연결 설정을 가져올 수 없습니다.");
  }
}
```

## 🛡️ 보안 및 품질 관리

### 배포 전 필수 체크

- `fdk validate` 통과 확인
- 하드코딩된 API 키/도메인 검색: `grep -r "wedosoft\|Ug9H1cKCZZtZ4haamBy"`
- iparams 기본값이 빈 문자열인지 확인
- JavaScript 구문 오류 검사

### 코드 품질

- 모든 함수에 한글 독스트링 작성
- 비즈니스 로직에 상세한 한글 주석
- 에러 처리 및 로깅 필수
- 타입 안전성 검증 (Python-JavaScript 간)

## 📁 주요 파일 구조

```
project-a/
├── backend/          # Python FastAPI 백엔드
│   ├── api/         # FastAPI 엔드포인트
│   ├── core/        # 핵심 비즈니스 로직
│   ├── freshdesk/   # Freshdesk API 연동
│   └── data/        # 데이터 처리
├── frontend/        # Freshdesk FDK 앱
│   ├── app/         # 메인 앱 코드
│   ├── config/      # FDK 설정
│   └── manifest.json
├── .vscode/         # VS Code 설정
└── tasks/           # Task Master 작업 관리
```

## 🎯 핵심 API 엔드포인트 (9개만 유지)

1. `/init` - 티켓 초기 데이터 (요약, 유사 티켓, 추천 솔루션)
2. `/query` - AI 채팅 (자연어 요청 처리)
3. `/generate_reply` - 추천 답변 생성
4. `/ingest` - 관리자용 데이터 수집
5. `/health` - 헬스체크
6. `/metrics` - 성능 메트릭
7. `/query/stream` - 실시간 스트리밍 채팅
8. `/generate_reply/stream` - 실시간 스트리밍 답변
9. `/attachments/*` - 첨부파일 접근

## 🔄 동적 멀티테넌트 처리

### 프론트엔드에서 백엔드로 헤더 전달

```javascript
const headers = {
  "X-Freshdesk-Domain": currentDomain,
  "X-Freshdesk-API-Key": currentApiKey,
  "Content-Type": "application/json",
};
```

### 백엔드에서 company_id 기반 데이터 격리

```python
company_id = extract_company_id(x_freshdesk_domain)
# Qdrant 검색 시 company_id 필터 적용
```

## 📝 자연어 명령 대표 패턴

- "이 문제 관련 자료 찾아줘"
- "비슷한 문제 해결 사례 찾아줘"
- "이 이슈의 해결책 제안해줘"
- "이 문제에 대한 대응 방법은?"

## ⚠️ 주의사항

### FDK 관련

- `fdk run` 실행 전 구문 오류 없는지 확인
- iparams.html과 iparams.json 중 하나만 존재해야 함
- manifest.json 권한 설정 정확히 확인

### 백엔드 관련

- 환경변수 설정 필수 (FRESHDESK_DOMAIN, QDRANT_URL 등)
- Docker 컨테이너 실행 시 볼륨 마운트 확인
- LLM API 키 설정 및 Rate limit 고려

### 디버깅 관련

- VS Code 디버거 사용 시 FDK 서버 개발 모드 실행 필수
- Chrome DevTools에서 소스맵 확인
- 중단점 비활성화 시 서버 재시작 및 브라우저 캐시 삭제

---

**🔥 핵심 원칙: 모든 작업은 제안 → 컨펌 → 실행 순서를 반드시 따르며, 사용자의 명시적 승인 없이는 어떤 파일도 수정하지 않습니다.**
