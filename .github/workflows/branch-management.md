# Project-A 브랜치 관리 가이드 (AI-Staging 중심)

## 🌿 브랜치 구조 개요

```bash
main (production)
├── dev (개발 통합)
├── ai-staging (AI 코드 통합 및 검증) ⭐ 핵심!
├── codex/feature-name (ChatGPT/Claude 생성)
├── copilot/feature-name (GitHub Copilot 생성)
└── feature/manual-feature (수동 개발)
```

## 🔄 AI 코드 통합 워크플로우

### 1단계: AI 도구별 개발
- `codex/*`: ChatGPT/Claude가 생성한 코드
- `copilot/*`: GitHub Copilot이 생성한 코드

### 2단계: AI-Staging 통합 ⭐
- 모든 AI 코드는 `ai-staging`으로 병합
- 통합 테스트 및 충돌 해결
- AI 도구 간 코드 호환성 검증

### 3단계: 단계별 승격
- `ai-staging` → `dev` → `main`
- 각 단계에서 철저한 테스트 수행

## 🤖 AI-Staging 중심 브랜치 관리

### 1. Codex 브랜치 작업
```bash
# Codex 전용 브랜치 생성
git checkout -b codex/langchain-parallel-processing

# Codex가 생성한 코드 작업
git add .
git commit -m "feat(codex): LangChain RunnableParallel 적용

- asyncio.gather를 RunnableParallel로 대체
- 성능 최적화 및 코드 가독성 향상
- Phase 2 리팩토링 완료

Generated-by: ChatGPT-4
Reviewed-by: [검토자명]"

git push origin codex/langchain-parallel-processing
```

### 2. Copilot 브랜치 작업
```bash
# Copilot 전용 브랜치 생성
git checkout -b copilot/api-error-handling

# Copilot 제안 코드 적용
git add .
git commit -m "feat(copilot): API 에러 핸들링 개선

- FastAPI 예외 처리 강화
- 타입 힌트 추가
- 로깅 개선

Generated-by: GitHub-Copilot
Co-authored-by: github-copilot[bot]"

git push origin copilot/api-error-handling
```

### 3. AI-Staging 통합 프로세스 ⭐
```bash
# ai-staging 브랜치로 이동 (없으면 생성)
git checkout ai-staging || git checkout -b ai-staging

# 각 AI 브랜치를 순차적으로 병합
git merge codex/langchain-parallel-processing
git merge copilot/api-error-handling

# 충돌 해결 및 통합 테스트
git add .
git commit -m "integrate: AI 코드 통합

- Codex: LangChain 병렬처리 개선
- Copilot: API 에러 핸들링 강화
- 통합 테스트 완료
- 타입 충돌 해결

Integrates: codex/langchain-parallel-processing, copilot/api-error-handling"

git push origin ai-staging
```

### 4. AI-Staging 검증 및 테스트
```bash
# ai-staging 브랜치에서 종합 테스트 실행
git checkout ai-staging

# 백엔드 테스트
cd backend
python -m pytest tests/ -v --cov=backend --cov-report=html

# API 서버 기동 테스트
uvicorn backend.api.main:app --reload &
sleep 5

# API 엔드포인트 테스트
curl -X GET "http://localhost:8000/health"
curl -X POST "http://localhost:8000/init/12345" -H "Content-Type: application/json" -d '{"email_body": "test"}'

# 프론트엔드 검증 (있는 경우)
cd frontend
fdk validate
fdk run --test

# 테스트 통과 확인 후 종료
pkill -f "uvicorn"
```

### 5. dev 브랜치 병합
```bash
# ai-staging 테스트 통과 후 dev로 병합
git checkout dev
git pull origin dev  # 최신 상태 확인

# ai-staging 병합
git merge ai-staging

# 최종 통합 테스트
npm test  # 또는 해당 프로젝트의 테스트 명령

git push origin dev
```

### 6. main 브랜치 배포
```bash
# dev 브랜치가 안정적인 경우 main으로 병합
git checkout main
git pull origin main

git merge dev
git tag -a v1.2.0 -m "Release v1.2.0: AI 통합 개선사항"
git push origin main --tags
```

## 📝 브랜치 네이밍 규칙

### AI 제공자별 분류 (권장)
- `codex/feature-name`: ChatGPT/Claude가 생성한 코드
- `codex/optimization-name`: ChatGPT/Claude 최적화 코드
- `copilot/feature-name`: GitHub Copilot이 생성한 코드
- `copilot/refactor-component`: GitHub Copilot 리팩토링 코드

### 통합 AI 분류 (대안)
- `ai/backend-optimization`: 백엔드 관련 AI 코드 (모든 AI 도구)
- `ai/frontend-improvements`: 프론트엔드 관련 AI 코드
- `ai/documentation-updates`: 문서 관련 AI 코드

### 수동 개발
- `feature/user-story`: 새로운 기능 개발
- `bugfix/issue-description`: 버그 수정
- `hotfix/critical-issue`: 긴급 수정
- `chore/maintenance-task`: 유지보수 작업

### 검토 브랜치
- `review/codex-feature-name`: Codex 코드 검토용
- `review/copilot-feature-name`: Copilot 코드 검토용
- `review/ai-integration`: AI 코드 통합 검토용
- `staging/release-candidate`: 릴리즈 후보

## ⚠️ 주의사항

1. **AI 코드 직접 dev 병합 금지**
   - Codex/Copilot 브랜치는 반드시 `review/` 브랜치를 거쳐야 함
   - 수동 코드 리뷰 필수
   - AI 도구별 코드 품질 차이 고려

2. **AI 도구별 특성 고려**
   - **Codex**: 대규모 리팩토링, 아키텍처 변경에 강함
   - **Copilot**: 함수/메서드 레벨 개선, 자동완성에 강함
   - 각 도구의 강점에 맞는 작업 분배

3. **테스트 커버리지 확인**
   - 단위 테스트 통과 확인
   - 통합 테스트 실행
   - API 엔드포인트 검증
   - AI 생성 코드의 엣지 케이스 검증

4. **문서화 업데이트**
   - API 문서 업데이트
   - README 수정사항 반영
   - 변경 로그에 AI 도구 명시
   - 코드 생성 도구별 기여도 추적

5. **보안 검토**
   - API 키 하드코딩 확인
   - 권한 설정 검토
   - 입력 검증 로직 확인

## 🚀 자동화 도구

### Pre-commit Hook (AI 코드 검증 강화)
```bash
# .git/hooks/pre-commit
#!/bin/sh

# 기본 코드 품질 검사
python -m black backend/
python -m flake8 backend/
python -m pytest tests/ --tb=short

# AI 생성 코드 특별 검증
if git diff --cached --name-only | grep -E "(codex|copilot)" > /dev/null; then
    echo "🤖 AI 생성 코드 감지됨. 추가 검증 실행..."
    
    # 타입 힌트 검증
    python -m mypy backend/ --ignore-missing-imports
    
    # 보안 스캔
    bandit -r backend/ -f json -o security-report.json
    
    # API 문서 업데이트 확인
    if [ ! -f "docs/api-updated.flag" ]; then
        echo "⚠️  API 문서 업데이트가 필요할 수 있습니다."
    fi
fi
```

### CI/CD 파이프라인 (AI-Staging 중심)
```yaml
# .github/workflows/ai-staging-pipeline.yml
name: AI-Staging Pipeline

on:
  push:
    branches: [ 'codex/**', 'copilot/**', 'ai-staging' ]
  pull_request:
    branches: [ 'ai-staging', 'dev' ]

jobs:
  # AI 도구별 기본 검증
  ai-code-validation:
    if: startsWith(github.ref, 'refs/heads/codex/') || startsWith(github.ref, 'refs/heads/copilot/')
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: |
          pip install -r backend/requirements.txt
          pip install pytest black flake8 mypy bandit
      
      - name: Code quality checks
        run: |
          black --check backend/
          flake8 backend/
          mypy backend/ --ignore-missing-imports
          bandit -r backend/ -f json -o security-report.json
      
      - name: Run tests
        run: pytest backend/tests/ -v

  # AI-Staging 통합 테스트 (핵심!)
  ai-staging-integration:
    if: github.ref == 'refs/heads/ai-staging'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: pip install -r backend/requirements.txt
      
      - name: AI 통합 테스트
        run: |
          # 백엔드 API 서버 시작
          uvicorn backend.api.main:app --host 0.0.0.0 --port 8000 &
          sleep 10
          
          # 핵심 API 엔드포인트 테스트
          curl -f http://localhost:8000/health || exit 1
          
          # LangChain 통합 테스트 (Codex 개선사항)
          pytest backend/tests/test_llm_router.py -v
          
          # API 에러 핸들링 테스트 (Copilot 개선사항)
          pytest backend/tests/test_error_handling.py -v
          
          # 전체 통합 테스트
          pytest backend/tests/ -v --cov=backend --cov-report=xml
          
          # 프로세스 정리
          pkill -f uvicorn
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
      
      - name: Slack 알림 (성공)
        if: success()
        run: |
          curl -X POST -H 'Content-type: application/json' \
            --data '{"text":"✅ AI-Staging 통합 테스트 성공! dev 브랜치 병합 준비 완료"}' \
            ${{ secrets.SLACK_WEBHOOK_URL }}
      
      - name: Slack 알림 (실패)
        if: failure()
        run: |
          curl -X POST -H 'Content-type: application/json' \
            --data '{"text":"❌ AI-Staging 통합 테스트 실패. 수동 검토 필요"}' \
            ${{ secrets.SLACK_WEBHOOK_URL }}

  # Dev 브랜치 최종 검증
  dev-deployment-check:
    if: github.ref == 'refs/heads/dev'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Production readiness check
        run: |
          echo "🚀 Dev 브랜치 배포 준비 상태 확인"
          # 프로덕션 배포 전 최종 검증 로직
```

## 📊 브랜치 정리 (AI-Staging 중심)

### AI-Staging 기반 브랜치 정리
```bash
# 1. AI-Staging에 병합된 AI 브랜치 정리
git checkout ai-staging
git branch --merged ai-staging | grep -E "(codex|copilot)/" | xargs -n 1 git branch -d

# 2. Dev에 병합된 AI-Staging 정리
git checkout dev  
git branch --merged dev | grep "ai-staging" | xargs -n 1 git branch -d

# 3. 오래된 AI 브랜치 정리 (7일 이상)
git for-each-ref --format='%(refname:short) %(committerdate)' refs/heads/ | \
  awk '$2 <= "'$(date -d '7 days ago' --iso-8601)'"' | \
  grep -E "(codex|copilot)/" | \
  awk '{print $1}' | xargs -n 1 git branch -D

# 4. 원격 브랜치 정리
git remote prune origin
```

### 브랜치 수명 관리 (AI-Staging 기준)
- **Codex/Copilot 브랜치**: AI-Staging 병합 후 즉시 삭제
- **AI-Staging 브랜치**: Dev 병합 확인 후 삭제 (보통 24시간 보관)
- **Feature 브랜치**: 릴리즈 후 삭제
- **Main/Dev 브랜치**: 영구 보관

### AI-Staging 상태 모니터링
```bash
# AI-Staging 브랜치 상태 확인
git log --oneline ai-staging ^dev | head -10

# 병합 대기 중인 AI 브랜치 확인
git branch --no-merged ai-staging | grep -E "(codex|copilot)/"

# AI-Staging과 Dev 브랜치 차이 확인
git diff dev..ai-staging --stat

# AI 코드 기여도 추적 (AI-Staging 기준)
git log --oneline --grep="integrate: AI 코드 통합" --since="1 month ago" | wc -l
git log --oneline ai-staging --grep="Generated-by:" --since="1 month ago" | wc -l
```

## 📈 성과 측정 (AI-Staging 기준)

### AI 도구 효율성 분석
- **통합 품질**: AI-Staging에서의 충돌 발생률 추적
- **배포 성공률**: AI-Staging → Dev → Main 성공률 측정
- **개발 속도**: AI 브랜치 → AI-Staging 통합 시간 추적
- **테스트 커버리지**: AI 통합 코드의 테스트 품질 분석

### AI-Staging 대시보드 메트릭
```bash
# AI-Staging 브랜치 건강도 체크
echo "📊 AI-Staging 상태 대시보드"
echo "=================================="

# 1. 대기 중인 AI 브랜치 수
echo "🔄 병합 대기 브랜치: $(git branch --no-merged ai-staging | grep -E "(codex|copilot)/" | wc -l)개"

# 2. 최근 AI-Staging 활동
echo "📅 최근 AI-Staging 커밋: $(git log -1 --pretty=format:'%cr' ai-staging)"

# 3. AI vs 수동 개발 비율 (최근 1개월)
AI_COMMITS=$(git log --oneline ai-staging --grep="integrate: AI" --since="1 month ago" | wc -l)
MANUAL_COMMITS=$(git log --oneline dev --grep="feat:" --invert-grep --grep="integrate: AI" --since="1 month ago" | wc -l)
echo "🤖 AI/수동 비율: ${AI_COMMITS}/${MANUAL_COMMITS}"

# 4. 테스트 성공률
echo "✅ AI-Staging 테스트 성공률: 확인 필요 (CI/CD 로그 참조)"
```

---

## 🚀 실전 사용 가이드

### 일반적인 AI 개발 워크플로우

```bash
# 1. 새로운 AI 작업 시작
git checkout dev
git pull origin dev
git checkout -b codex/new-feature

# 2. AI 도구로 코드 작성 후
git add .
git commit -m "feat(codex): 새로운 기능 구현

Generated-by: ChatGPT-4"
git push origin codex/new-feature

# 3. AI-Staging으로 통합
git checkout ai-staging
git pull origin ai-staging
git merge codex/new-feature

# 4. 통합 테스트 후 Push
git push origin ai-staging

# 5. CI 통과 확인 후 Dev 병합
git checkout dev
git merge ai-staging
git push origin dev
```

### 긴급 상황 대응

```bash
# AI-Staging에서 문제 발생 시 롤백
git checkout ai-staging
git reset --hard HEAD~1  # 마지막 병합 취소
git push --force-with-lease origin ai-staging

# 특정 AI 브랜치만 제외하고 재통합
git checkout ai-staging
git reset --hard dev  # AI-Staging 초기화
git merge codex/good-feature  # 문제없는 브랜치만 병합
git push --force-with-lease origin ai-staging
```

### AI-Staging 브랜치 생성 (최초 1회)

```bash
# 프로젝트에 AI-Staging 브랜치가 없는 경우
git checkout dev
git checkout -b ai-staging
git push origin ai-staging

# 브랜치 보호 규칙 설정 (GitHub)
gh api repos/:owner/:repo/branches/ai-staging/protection \
  --method PUT \
  --field required_status_checks='{"strict":true,"contexts":["AI-Staging Pipeline"]}' \
  --field enforce_admins=true
```
