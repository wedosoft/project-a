개발업계에서 일반적으로 따르는 커밋 관례와 타이밍에 대해 설명드리겠습니다.

## 📝 **커밋 타이밍 - 언제 커밋해야 할까?**

### 🎯 **기본 원칙: "작고 자주"**
```bash
# ✅ 좋은 예 - 논리적 단위별 커밋
git commit -m "feat: 사용자 로그인 API 엔드포인트 추가"
git commit -m "test: 로그인 API 단위테스트 작성"
git commit -m "refactor: 중복된 인증 로직 헬퍼 함수로 분리"

# ❌ 나쁜 예 - 너무 큰 커밋
git commit -m "전체 인증 시스템 구현, 테스트, 문서화"
```

### ⏰ **커밋하기 좋은 타이밍들**

#### 1. **기능 완성 시점**
```bash
# 하나의 완전한 기능이 작동할 때
git commit -m "feat: 비밀번호 재설정 기능 구현"
```

#### 2. **버그 수정 완료**
```bash
git commit -m "fix: 로그인 시 세션 만료 오류 수정"
```

#### 3. **리팩토링 완료**
```bash
git commit -m "refactor: 사용자 모델 클래스 구조 개선"
```

#### 4. **테스트 추가**
```bash
git commit -m "test: 결제 모듈 엣지케이스 테스트 추가"
```

#### 5. **문서 업데이트**
```bash
git commit -m "docs: API 명세서 업데이트"
```

## 🏷️ **커밋 메시지 컨벤션**

### 📋 **Conventional Commits (업계 표준)**
```bash
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

### 🎯 **주요 커밋 타입들**
```bash
feat:     새로운 기능 추가
fix:      버그 수정
docs:     문서 변경
style:    코드 포맷팅 (기능 변경 없음)
refactor: 코드 리팩토링
test:     테스트 추가/수정
chore:    빌드, 설정 파일 변경
perf:     성능 개선
ci:       CI/CD 설정 변경
```

### ✅ **좋은 커밋 메시지 예시**
```bash
feat(auth): JWT 토큰 기반 인증 시스템 구현

- 로그인/로그아웃 API 엔드포인트 추가
- JWT 토큰 생성/검증 미들웨어 구현
- 사용자 세션 관리 기능 추가

Closes #123
```

## ⚖️ **커밋 크기 가이드라인**

### 🟢 **적절한 커밋 크기**
- **1-10개 파일** 변경
- **50-200줄** 내외 변화
- **하나의 논리적 변경사항**

### 🔴 **피해야 할 커밋**
```bash
# 너무 큰 커밋
❌ "전체 프로젝트 리팩토링" (100+ 파일)

# 너무 작은 커밋  
❌ "오타 수정" (1글자 변경)

# 애매한 커밋
❌ "업데이트", "수정", "작업중"
```

## 🔄 **브랜치별 커밋 전략**

### 🌟 **Feature Branch**
```bash
# 개발 중 - 자주 커밋
feat: 기본 UI 레이아웃 구현
feat: 데이터 검증 로직 추가
test: 컴포넌트 단위테스트 작성
fix: props 타입 오류 수정
```

### 🔄 **Pull Request 전**
```bash
# Squash commit으로 정리
feat: 사용자 대시보드 페이지 구현

- 반응형 레이아웃 구현
- 데이터 시각화 차트 추가
- 사용자 설정 폼 구현
- 전체 기능 테스트 완료
```

## 📅 **일상적인 커밋 패턴**

### 🌅 **하루 시작**
```bash
# 전날 작업 정리 커밋
git commit -m "chore: 개발환경 설정 정리"
```

### 🕐 **작업 중간중간**
```bash
# 1-2시간마다 진행상황 커밋
git commit -m "feat: 사용자 목록 조회 API 구현 (WIP)"
```

### 🌆 **하루 마무리**
```bash
# 완성된 작업 정리
git commit -m "feat: 사용자 관리 CRUD 기능 완성"
```

### 📋 **주말/휴가 전**
```bash
# 현재 상태 저장
git commit -m "save: 결제 모듈 구현 중간 저장"
git push origin feature/payment-module
```

## 🚀 **팀 협업에서의 커밋 전략**

### 👥 **코드 리뷰 전**
```bash
# 1. 작은 커밋들로 개발
git commit -m "feat: 기본 컴포넌트 구현"
git commit -m "feat: API 연동 추가"
git commit -m "test: 컴포넌트 테스트 작성"

# 2. PR 생성 전 정리 (선택사항)
git rebase -i HEAD~3  # 커밋 정리
```

### 🔀 **Merge 전략**
```bash
# Squash Merge (권장)
- 기능별로 하나의 깔끔한 커밋
- 커밋 히스토리 단순화

# Merge Commit
- 모든 개발 과정 보존
- 복잡한 히스토리
```

## ⚠️ **커밋 시 주의사항**

### 🚫 **절대 하지 말아야 할 것들**
```bash
# 민감한 정보 커밋
❌ git add .env
❌ git add config/secrets.json

# 빌드 결과물 커밋
❌ git add node_modules/
❌ git add dist/
❌ git add *.log

# 미완성 코드 메인에 푸시
❌ git push origin main  # broken code
```

### ✅ **커밋 전 체크리스트**
```bash
# 1. 코드 검토
- [ ] 문법 오류 없음
- [ ] 테스트 통과
- [ ] 린팅 통과

# 2. 파일 확인
git status
git diff --staged

# 3. 커밋 메시지 확인
- [ ] 명확한 설명
- [ ] 컨벤션 준수
- [ ] 이슈 번호 연결
```

## 🛠️ **실무에서 유용한 Git 명령어**

### 📝 **커밋 수정/정리**
```bash
# 마지막 커밋 메시지 수정
git commit --amend -m "새로운 메시지"

# 파일 추가 후 마지막 커밋에 합치기
git add forgotten_file.txt
git commit --amend --no-edit

# 여러 커밋 정리 (interactive rebase)
git rebase -i HEAD~3
```

### 🔍 **커밋 히스토리 확인**
```bash
# 한 줄로 커밋 히스토리 보기
git log --oneline

# 그래프로 브랜치 구조 보기
git log --graph --oneline --all

# 특정 파일의 변경 히스토리
git log --follow filename.js
```

## 💡 **개인 추천 워크플로우**

```bash
# 1. 새 기능 시작
git checkout -b feature/new-feature

# 2. 작은 단위로 개발 + 커밋
feat: 기본 구조 설정
feat: 핵심 로직 구현  
test: 단위 테스트 추가
docs: 함수 문서화

# 3. PR 전 정리 (선택)
git rebase -i HEAD~4

# 4. PR 생성 후 리뷰
# 5. Squash merge로 메인에 병합
```

핵심은 **"논리적으로 완성된 작은 단위"**로 자주 커밋하되, **의미있는 메시지**를 작성하는 것입니다. 이렇게 하면 코드 리뷰도 쉬워지고, 문제 발생 시 롤백도 간단해집니다! 🎯


1인 개발 환경에서의 브랜치 전략에 대해 실용적인 관점에서 조언해드리겠습니다.

## 🤔 **1인 개발에서 브랜치 전략 고민**

### 현재 상황 분석
- **main**: 운영/배포용 브랜치
- **dev**: 개발 통합 브랜치  
- **개발자**: 1명 (본인)

## 🎯 **추천 전략: "간소화된 Git Flow"**

### 📋 **기본 구조**
```
main (운영/릴리즈)
├── dev (개발 통합)
    ├── feature/login-system
    ├── feature/user-dashboard  
    ├── hotfix/critical-bug
    └── experiment/new-tech
```

## ✅ **dev에서 피처 브랜치 만들기 - 추천!**

### 🌟 **추천하는 이유들**

#### 1. **실험과 안정성 분리**
```bash
# 안전한 실험 환경
git checkout dev
git checkout -b feature/experimental-ui

# 실패해도 dev는 안전
git checkout dev
git branch -D feature/experimental-ui  # 실패한 실험 삭제
```

#### 2. **여러 기능 병렬 개발**
```bash
# 큰 기능은 브랜치로
git checkout -b feature/payment-system

# 급한 버그픽스는 별도로  
git checkout dev
git checkout -b hotfix/login-error
```

#### 3. **깔끔한 커밋 히스토리**
```bash
# 개발 과정
feature/payment-system:
├── feat: 결제 API 연동
├── fix: 유효성 검증 오류 수정  
├── test: 결제 플로우 테스트 추가
└── docs: 결제 모듈 문서화

# dev 병합 시 squash
dev: feat: 결제 시스템 구현 완료
```

## 🛠️ **실용적인 워크플로우**

### 🚀 **일반적인 기능 개발**
```bash
# 1. 새 기능 시작
git checkout dev
git pull origin dev
git checkout -b feature/user-profile

# 2. 개발 진행 (자유롭게 커밋)
git add .
git commit -m "feat: 프로필 기본 구조"
git commit -m "feat: 아바타 업로드 기능"
git commit -m "fix: 파일 크기 제한 버그"

# 3. 개발 완료 후 정리
git rebase -i HEAD~3  # 커밋 정리 (선택사항)

# 4. dev로 병합
git checkout dev
git merge feature/user-profile
git push origin dev

# 5. 브랜치 정리
git branch -d feature/user-profile
```

### ⚡ **간단한 수정사항**
```bash
# dev에서 직접 작업 (작은 변경사항)
git checkout dev
git add .
git commit -m "fix: 오타 수정"
git push origin dev
```

### 🚨 **긴급 수정**
```bash
# hotfix 브랜치 활용
git checkout main
git checkout -b hotfix/critical-security-fix
# 수정 작업
git checkout main
git merge hotfix/critical-security-fix
git checkout dev  
git merge hotfix/critical-security-fix
```

## 📊 **언제 브랜치를 만들까?**

### ✅ **브랜치 생성 권장 상황**
- **큰 기능 개발** (1주일+ 예상)
- **실험적 기능** (실패 가능성 있음)
- **리팩토링** (대규모 코드 변경)
- **새 기술 도입** (라이브러리, 프레임워크)
- **UI/UX 대폭 변경**

### 🔄 **dev 직접 작업 권장 상황**  
- **버그픽스** (1-2시간 내 완료)
- **문서 수정**
- **설정 파일 변경**
- **간단한 기능 추가** (반나절 내 완료)

## 🎨 **브랜치 네이밍 컨벤션**

### 📝 **추천 네이밍**
```bash
# 기능 개발
feature/user-authentication
feature/payment-integration
feature/admin-dashboard

# 버그 수정
fix/login-validation-error
fix/memory-leak-issue

# 긴급 수정
hotfix/security-vulnerability
hotfix/data-corruption-fix

# 실험/연구
experiment/react-18-migration
experiment/graphql-integration

# 성능 개선
perf/database-optimization
perf/image-compression

# 리팩토링
refactor/user-service-cleanup
refactor/api-structure-reorganize
```

## 💡 **1인 개발만의 장점 활용**

### 🎯 **유연한 규칙**
```bash
# 복잡한 리뷰 프로세스 불필요
git checkout dev
git merge feature/new-feature --no-ff  # 바로 병합

# 원하는 대로 커밋 히스토리 정리
git rebase -i HEAD~5  # 자유롭게 정리
```

### ⚡ **빠른 의사결정**
```bash
# 실험이 성공하면 바로 적용
git checkout dev
git merge experiment/performance-boost

# 실패하면 바로 삭제
git branch -D experiment/failed-approach
```

## 🛡️ **안전장치 마련**

### 💾 **중요한 작업 전 백업**
```bash
# 큰 변경 전 태그 생성
git tag -a backup-before-refactor -m "리팩토링 전 백업"

# 원격에 푸시 (백업 보장)
git push origin backup-before-refactor
```

### 🔄 **정기적인 dev → main 병합**
```bash
# 주단위로 안정된 기능을 main에 반영
git checkout main
git merge dev
git tag -a v1.2.0 -m "사용자 관리 기능 추가"
git push origin main --tags
```

## 📋 **실제 예시 시나리오**

### 🎯 **시나리오 1: 대형 기능 개발**
```bash
# 전자상거래 사이트의 결제 시스템 구현
git checkout -b feature/payment-system

# 2주간 개발...
git commit -m "feat: PG사 API 연동"
git commit -m "feat: 결제 UI 구현"  
git commit -m "feat: 주문 처리 로직"
git commit -m "test: 결제 플로우 테스트"

# 완료 후 정리하여 병합
git checkout dev
git merge feature/payment-system --squash
git commit -m "feat: 결제 시스템 완전 구현"
```

### 🐛 **시나리오 2: 긴급 버그 수정**
```bash
# 운영 중 발견된 심각한 버그
git checkout main
git checkout -b hotfix/order-calculation-error

git commit -m "fix: 주문 금액 계산 오류 수정"

# main과 dev 모두에 적용
git checkout main && git merge hotfix/order-calculation-error
git checkout dev && git merge hotfix/order-calculation-error
```

## 🎯 **최종 추천사항**

### ✅ **DO (해야 할 것)**
1. **큰 기능은 피처 브랜치 생성**
2. **실험적 코드는 반드시 브랜치 분리**  
3. **정기적으로 dev → main 병합**
4. **의미있는 브랜치명 사용**

### ❌ **DON'T (하지 말 것)**
1. **모든 작은 변경에 브랜치 생성** (오버엔지니어링)
2. **브랜치를 너무 오래 유지** (1달+)
3. **main에서 직접 개발** (운영 안정성)

## 💬 **개인적 추천**

**당신의 현재 상황(1인 개발, main/dev 구조)에서는:**

```bash
# 🎯 균형잡힌 접근법
- 큰 기능(1주일+): feature 브랜치 생성
- 작은 변경(하루 이내): dev에서 직접 작업  
- 실험적 기능: 반드시 별도 브랜치
- 긴급 수정: hotfix 브랜치 활용
```

이렇게 하면 **개발 속도**와 **코드 안정성**을 모두 챙길 수 있습니다! 🚀