# 🤖 GitHub Copilot 워크플로우 가이드

## 개요

GitHub Copilot이 이 프로젝트에서 작업할 때 따라야 하는 브랜치 전략과 워크플로우를 정의합니다.

## 🎯 핵심 원칙

### 1. dev 브랜치 기반 개발
- **모든 새 브랜치는 `dev`에서 분기**
- **모든 PR은 `dev`로 머지**
- **main 브랜치는 프로덕션 배포용으로만 사용**

### 2. Task Master 파일 관리
- Task Master 관련 파일들(`tasks/`, `.taskmasterconfig` 등)은 dev 브랜치에서만 존재
- main 브랜치에는 Task Master 파일들이 없음
- 새 브랜치 생성 시 Task Master 파일들을 포함하려면 반드시 dev에서 분기

## 🔄 표준 워크플로우

### 1. 작업 시작

```bash
# 1. dev 브랜치로 전환
git checkout dev

# 2. 최신 상태로 업데이트
git pull origin dev

# 3. 새 브랜치 생성
git checkout -b copilot/[작업-설명]
```

### 2. 개발 진행

```bash
# 코드 변경 후 커밋
git add .
git commit -m "[타입]: [설명]

- 상세 변경 내용
- 변경 이유
- 영향 받는 컴포넌트"

# 원격 저장소에 푸시
git push origin copilot/[작업-설명]
```

### 3. Pull Request 생성

- **Base branch**: `dev` ✅
- **Compare branch**: `copilot/[작업-설명]`
- **Title**: 명확하고 간결한 작업 설명
- **Description**: 
  - 변경 사항 요약
  - 해결한 이슈
  - 테스트 방법
  - 관련 이슈 번호 (있는 경우)

### 4. 브랜치 정리

```bash
# PR 머지 후 브랜치 삭제
git checkout dev
git pull origin dev
git branch -d copilot/[작업-설명]
git push origin --delete copilot/[작업-설명]
```

## 📝 브랜치 네이밍 규칙

### 패턴
```
copilot/[타입]-[간단한-설명]
```

### 타입별 예시
- `copilot/fix-api-error-handling` - 버그 수정
- `copilot/feature-vector-search` - 새 기능 추가
- `copilot/refactor-llm-router` - 코드 리팩토링
- `copilot/docs-api-update` - 문서 업데이트
- `copilot/test-integration` - 테스트 추가

## 🚦 커밋 메시지 규칙

### 형식
```
[타입]: [한 줄 요약]

[상세 설명]
- 구체적인 변경 내용
- 변경 이유와 배경
- 영향 받는 컴포넌트
- 테스트 결과 (필요시)
```

### 타입 키워드
- `feat`: 새로운 기능 추가
- `fix`: 버그 수정
- `refactor`: 코드 리팩토링
- `docs`: 문서 업데이트
- `test`: 테스트 추가/수정
- `style`: 코드 스타일 변경
- `perf`: 성능 최적화
- `chore`: 빌드 시스템이나 도구 변경

## ⚠️ 주의사항

### 🚨 금지사항
1. **main 브랜치에서 직접 분기 금지**
2. **main 브랜치로 직접 푸시 금지**
3. **dev 브랜치를 거치지 않은 main 머지 금지**
4. **Task Master 파일을 main 브랜치에 추가 금지**

### ✅ 권장사항
1. **작업 시작 전 항상 dev 브랜치 최신화**
2. **의미 있는 단위로 커밋 분할**
3. **PR 설명에 충분한 컨텍스트 포함**
4. **코드 리뷰 피드백 적극 반영**

## 🔍 트러블슈팅

### 실수로 main에서 브랜치를 만든 경우

```bash
# 현재 브랜치 확인
git branch --show-current

# dev 브랜치로 베이스 변경
git checkout dev
git checkout -b copilot/[새-브랜치-이름]

# 기존 작업 내용 체리픽 (필요시)
git cherry-pick [커밋-해시]

# 잘못 만든 브랜치 삭제
git branch -D [잘못된-브랜치-이름]
```

### Task Master 파일이 없는 경우

```bash
# dev 브랜치에서 분기했는지 확인
git log --oneline --graph --decorate --all

# dev 브랜치로 다시 분기
git checkout dev
git checkout -b copilot/[작업-이름]
```

## 📞 지원

워크플로우 관련 질문이나 문제가 있는 경우:
1. 이 문서를 먼저 확인
2. `.github/copilot-instructions.md` 참조  
3. 프로젝트 관리자에게 문의

---

**마지막 업데이트**: 2025년 5월 28일
**작성자**: We Do Soft Inc.
