# Claude 지침 관리 도구 사용 가이드 v2.1

> **claude-guide-manager.sh** - Claude Code 최적화를 위한 지침 관리 자동화 도구 (집-회사 동기화 지원)

## 📋 목차
- [개요](#-개요)
- [설치 및 설정](#-설치-및-설정)
- [명령어 레퍼런스](#-명령어-레퍼런스)
- [집-회사 동기화 관리](#-집-회사-동기화-관리)
- [사용 시나리오](#-사용-시나리오)
- [지침 구조](#-지침-구조)
- [워크트리 관리](#-워크트리-관리)
- [트러블슈팅](#-트러블슈팅)

## 🎯 개요

Claude 지침 관리 도구는 다음 문제를 해결합니다:
- **산재된 CLAUDE.md 파일들**로 인한 혼란
- **워크트리 간 지침 불일치**
- **집-회사 환경 간 지침 동기화** 어려움
- **Claude Code 사용 시 참조할 지침 파일 선택의 어려움**
- **프로젝트별 컨텍스트 관리의 복잡성**

### 주요 기능
- ✅ **지침 구조 자동 정리**: 중복 제거 및 계층적 구조 생성
- ✅ **워크트리 자동 동기화**: 모든 워크트리에 일관된 지침 적용
- ✅ **집-회사 동기화**: Git 기반 자동 동기화 + 개인 환경별 관리
- ✅ **작업 컨텍스트 관리**: 현재 작업에 맞는 지침 업데이트
- ✅ **시나리오별 가이드**: 작업 유형에 따른 맞춤 지침 추천
- ✅ **Claude Code 최적화**: 효과적인 Claude Code 사용법 안내

## 🛠️ 설치 및 설정

### 1. 스크립트 위치 확인
```bash
# 프로젝트 루트에서 실행
ls scripts/claude-guide-manager.sh
```

### 2. 실행 권한 부여
```bash
chmod +x scripts/claude-guide-manager.sh
```

### 3. 초기 설정 (최초 1회)
```bash
# 지침 구조 초기화
./scripts/claude-guide-manager.sh init
```

## 📖 명령어 레퍼런스

### 기본 사용법
```bash
./scripts/claude-guide-manager.sh [명령어] [옵션]
```

### 📋 전체 명령어 목록

| 명령어 | 단축 | 설명 | 예시 |
|--------|------|------|------|
| `init` | `i` | 지침 구조 초기화 및 정리 | `./scripts/claude-guide-manager.sh init` |
| `structure` | `s` | 새로운 지침 구조 표시 | `./scripts/claude-guide-manager.sh structure` |
| `context` | `ctx` | 현재 작업 컨텍스트 표시 | `./scripts/claude-guide-manager.sh context` |
| `full-context` | `full` | 전체 컨텍스트 (Git + 로컬) 표시 | `./scripts/claude-guide-manager.sh full-context` |
| `local-context` | `local` | 로컬 작업 컨텍스트 생성 | `./scripts/claude-guide-manager.sh local-context 집 "작업설명"` |
| `sync` | - | 워크트리에 지침 동기화 | `./scripts/claude-guide-manager.sh sync` |
| `status` | `st` | 워크트리 지침 상태 확인 | `./scripts/claude-guide-manager.sh status` |
| `optimize` | `opt` | Claude Code 최적화 가이드 | `./scripts/claude-guide-manager.sh optimize` |
| `recommend` | `rec` | 작업 유형별 가이드 추천 | `./scripts/claude-guide-manager.sh recommend performance` |
| `update-context` | `update` | 작업 컨텍스트 업데이트 | `./scripts/claude-guide-manager.sh update-context "성능 최적화"` |
| `help` | `h` | 도움말 표시 | `./scripts/claude-guide-manager.sh help` |

### 🔧 상세 명령어 설명

#### `init` - 지침 구조 초기화
```bash
./scripts/claude-guide-manager.sh init
```
**기능:**
- 기존 산재된 CLAUDE.md 파일들을 백업
- `.claude/` 폴더에 구조화된 가이드 생성
- 중복 제거 및 계층적 구조 생성
- 프로젝트 루트에 간소화된 CLAUDE.md 생성

**실행 결과:**
- `CLAUDE.md.backup.YYYYMMDD` 백업 파일들 생성
- `.claude/backend-guide.md` 생성
- `.claude/modules/` 폴더에 모듈별 가이드 생성

#### `structure` - 지침 구조 표시
```bash
./scripts/claude-guide-manager.sh structure
```
**출력 예시:**
```
🏗️ 새로운 Claude 지침 구조:

🌍 글로벌 원칙: /Users/username/.claude/CLAUDE.md

🏠 프로젝트 지침:
  📄 메인: CLAUDE.md (현재 작업 컨텍스트만)

📁 상세 가이드 (.claude/):
  🔧 백엔드: .claude/backend-guide.md
  🎨 프론트엔드: .claude/frontend-guide.md
  📦 모듈별 가이드:
    • database: .claude/modules/database.md
    • llm: .claude/modules/llm.md
    • search: .claude/modules/search.md
    • ingest: .claude/modules/ingest.md
```

#### `context` - 현재 작업 컨텍스트 표시
```bash
./scripts/claude-guide-manager.sh context
```
**기능:**
- 프로젝트 루트 CLAUDE.md에서 현재 작업 섹션 추출
- 작업 상태, 목표, 범위 등 표시

#### `sync` - 워크트리 동기화
```bash
./scripts/claude-guide-manager.sh sync
```
**기능:**
- 모든 워크트리에 현재 지침 복사
- CLAUDE.md, .claude/ 폴더, 관리 스크립트 동기화
- rsync를 사용한 효율적 파일 동기화

**실행 결과:**
```
🌳 워크트리 동기화를 시작합니다...

📁 워크트리 동기화: project-a-feature-branch
  ✅ CLAUDE.md 동기화 완료
  ✅ .claude/ 폴더 동기화 완료
  ✅ 관리 스크립트 동기화 완료

🎉 총 1개의 워크트리에 지침을 동기화했습니다.
```

#### `status` - 워크트리 상태 확인
```bash
./scripts/claude-guide-manager.sh status
```
**기능:**
- 각 워크트리의 지침 동기화 상태 확인
- MD5 해시를 사용한 파일 일치성 검증

**출력 예시:**
```
🌳 워크트리 지침 상태 확인:

📁 project-a-feature-branch:
  ✅ CLAUDE.md 동기화됨
  ✅ .claude 폴더 존재

📁 project-a-hotfix:
  ⚠️  CLAUDE.md 동기화 필요
  ❌ .claude 폴더 없음
```

#### `recommend` - 작업 유형별 가이드 추천
```bash
./scripts/claude-guide-manager.sh recommend [작업유형]
```

**지원 작업 유형:**
- `performance` / `성능`: 성능 최적화 작업
- `api` / `엔드포인트`: API 개발 작업
- `frontend` / `프론트엔드`: 프론트엔드 작업
- `database`: 데이터베이스 작업
- `llm`: LLM 관련 작업
- `search`: 검색 기능 작업

**예시:**
```bash
./scripts/claude-guide-manager.sh recommend performance
```

**출력:**
```
💡 작업 유형별 가이드 추천:

🚀 성능 최적화 작업:
  1. CLAUDE.md - 현재 성능 목표 확인
  2. .claude/backend-guide.md - 성능 최적화 패턴
  3. .claude/modules/database.md - DB 쿼리 최적화
```

#### `update-context` - 작업 컨텍스트 업데이트
```bash
./scripts/claude-guide-manager.sh update-context "작업 설명" [우선순위] [범위]
```

**파라미터:**
- `작업 설명` (필수): 현재 작업에 대한 간단한 설명
- `우선순위` (선택): 높음/중간/낮음 (기본값: 중간)
- `범위` (선택): 작업 범위 설명 (기본값: backend 최적화)

**예시:**
```bash
./scripts/claude-guide-manager.sh update-context "성능 최적화" "높음" "backend/api, backend/core"
```

#### `optimize` - Claude Code 최적화 가이드
```bash
./scripts/claude-guide-manager.sh optimize
```
**기능:**
- Claude Code 사용 시 최적 워크플로우 안내
- 파일 참조 순서 가이드
- 시나리오별 사용 팁 제공

## 🎬 사용 시나리오

### 시나리오 1: 새 프로젝트 시작
```bash
# 1. 지침 구조 초기화
./scripts/claude-guide-manager.sh init

# 2. 구조 확인
./scripts/claude-guide-manager.sh structure

# 3. 현재 작업 설정
./scripts/claude-guide-manager.sh update-context "프로젝트 초기 설정"
```

### 시나리오 2: 집에서 작업 시작 🏠
```bash
# 1. 최신 변경사항 동기화
git pull origin dev

# 2. 로컬 작업 컨텍스트 생성
./scripts/claude-guide-manager.sh local-context "집" "성능 최적화 작업"

# 3. 전체 컨텍스트 확인
./scripts/claude-guide-manager.sh full-context

# 4. Claude Code에서 사용
# "현재 full-context를 확인하고, 집 환경에서 성능 최적화 작업을 시작해주세요"
```

### 시나리오 3: 회사에서 작업 시작 🏢
```bash
# 1. 최신 변경사항 동기화
git pull origin dev

# 2. 로컬 작업 컨텍스트 생성
./scripts/claude-guide-manager.sh local-context "회사" "API 개발"

# 3. 전체 컨텍스트 확인
./scripts/claude-guide-manager.sh full-context

# 4. Claude Code에서 사용
# "현재 full-context를 확인하고, 회사 환경에서 API 개발을 진행해주세요"
```

### 시나리오 4: 성능 최적화 작업
```bash
# 1. 작업 컨텍스트 업데이트
./scripts/claude-guide-manager.sh update-context "API 성능 최적화" "높음"

# 2. 가이드 추천 확인
./scripts/claude-guide-manager.sh recommend performance

# 3. Claude Code에서 사용
# "현재 CLAUDE.md 컨텍스트를 확인하고, .claude/backend-guide.md 성능 섹션을 참조해주세요"
```

### 시나리오 5: 워크트리 작업
```bash
# 1. 새 워크트리 생성 후
git worktree add ../project-feature feature-branch

# 2. 지침 동기화
./scripts/claude-guide-manager.sh sync

# 3. 동기화 상태 확인
./scripts/claude-guide-manager.sh status
```

### 시나리오 6: 작업 완료 후 동기화 📤
```bash
# 1. 지침 파일 변경사항이 있다면 커밋
git add CLAUDE.md .claude/
git commit -m "docs: Claude 지침 업데이트"
git push origin dev

# 2. 워크트리 동기화
./scripts/claude-guide-manager.sh sync

# Note: 로컬 컨텍스트(CLAUDE.md.local)는 자동으로 Git에서 제외됨
```

### 시나리오 7: 모듈별 작업
```bash
# 1. 작업 가이드 확인
./scripts/claude-guide-manager.sh recommend llm

# 2. Claude Code에서 모듈별 지침 참조
# "LLM 최적화 작업입니다. .claude/modules/llm.md 가이드라인을 따라주세요"
```

## 🏗️ 지침 구조

### 파일 계층 구조
```
🌍 ~/.claude/CLAUDE.md
├── 전역 개발 원칙 (모든 프로젝트 공통)
├── Python/JavaScript 컨벤션
├── 보안/성능 원칙
└── 테스트 가이드라인

🏠 프로젝트루트/CLAUDE.md
├── 프로젝트 개요
├── 현재 작업 컨텍스트
├── Claude Code 사용 시나리오
└── 상세 지침 참조 링크

📁 프로젝트루트/.claude/
├── backend-guide.md      # 백엔드 아키텍처, 패턴
├── frontend-guide.md     # 프론트엔드 컴포넌트, FDK
└── modules/             # 모듈별 전문 가이드
    ├── database.md      # Qdrant, 쿼리 최적화
    ├── llm.md          # 다중 LLM, 캐싱, 성능
    ├── search.md       # 벡터 검색, 필터링
    └── ingest.md       # 데이터 수집, 배치 처리
```

### 참조 우선순위
1. **현재 작업**: `CLAUDE.md` (프로젝트 루트)
2. **영역별 가이드**: `.claude/backend-guide.md` 또는 `.claude/frontend-guide.md`
3. **모듈 전문**: `.claude/modules/[모듈명].md`
4. **글로벌 원칙**: `~/.claude/CLAUDE.md`

## 🌳 워크트리 관리

### 자동 동기화 메커니즘
- **파일 감지**: `git worktree list` 명령으로 워크트리 자동 감지
- **선택적 복사**: 메인 워크트리만 제외하고 모든 워크트리에 동기화
- **효율적 전송**: `rsync`를 사용한 차분 동기화
- **무결성 검증**: MD5 해시를 사용한 파일 일치성 확인

### 동기화되는 파일들
- `CLAUDE.md` (프로젝트 루트)
- `.claude/` 폴더 전체 (하위 폴더 포함)
- `scripts/claude-guide-manager.sh` (관리 도구)

### 워크트리별 독립성 유지
- 각 워크트리는 독립적인 `.git` 폴더 유지
- 지침 파일만 동기화, 소스 코드는 브랜치별로 독립적
- 워크트리별 작업 컨텍스트는 개별 관리 가능

## 🏠🏢 집-회사 동기화 관리

### 동기화 전략
Claude 지침 관리는 **이중 레벨 동기화**를 지원합니다:

1. **Git 관리 (집-회사 공유)**
   - `CLAUDE.md` - 프로젝트 공통 컨텍스트
   - `.claude/` 폴더 - 상세 가이드라인
   - `scripts/claude-guide-manager.sh` - 관리 도구

2. **로컬 관리 (개인 환경별)**
   - `CLAUDE.md.local` - 개인 작업 환경별 메모
   - Git 추적 제외 (`.gitignore`에 포함)

### 집-회사 워크플로우

#### **🏠 집에서 작업 시작**
```bash
# 1. 최신 변경사항 pull
git pull origin main

# 2. 로컬 작업 컨텍스트 생성
./scripts/claude-guide-manager.sh local-context "집" "성능 최적화 작업"

# 3. 전체 컨텍스트 확인
./scripts/claude-guide-manager.sh full-context
```

#### **🏢 회사에서 작업 시작**
```bash
# 1. 최신 변경사항 pull
git pull origin main

# 2. 로컬 작업 컨텍스트 생성
./scripts/claude-guide-manager.sh local-context "회사" "API 개발"

# 3. 전체 컨텍스트 확인
./scripts/claude-guide-manager.sh full-context
```

#### **📤 작업 완료 시 (집/회사 공통)**
```bash
# 1. 지침 파일 변경사항이 있다면 커밋
git add CLAUDE.md .claude/
git commit -m "docs: Claude 지침 업데이트"
git push origin main

# 2. 로컬 컨텍스트는 Git에 포함되지 않음 (자동)
```

### 새로운 명령어들

#### `full-context` - 전체 컨텍스트 표시
```bash
./scripts/claude-guide-manager.sh full-context
```
**기능:**
- Git 관리 프로젝트 컨텍스트와 로컬 개인 컨텍스트를 통합 표시
- 집-회사 동기화 상태 확인에 최적

**출력 예시:**
```
🏠🏢 전체 작업 컨텍스트:

📋 프로젝트 컨텍스트 (Git 동기화됨):
- **작업**: Claude 지침 구조 최적화
- **목표**: 지침 관리 간소화 및 일관성 확보
- **범위**: 전체 프로젝트 문서 구조
- **상태**: 진행 중

💻 로컬 작업 컨텍스트 (개인 환경):
- **위치**: 집
- **작업자**: alan
- **컴퓨터**: Alanui-MacBookPro  
- **날짜**: 2025-07-04
- **작업**: Claude 지침 시스템 개선
```

#### `local-context` - 로컬 작업 컨텍스트 생성
```bash
./scripts/claude-guide-manager.sh local-context <위치> <작업설명>
```

**파라미터:**
- `위치` (필수): "집" 또는 "회사" 등 작업 환경
- `작업설명` (필수): 현재 진행 중인 작업에 대한 설명

**기능:**
- 개인 작업 환경별 컨텍스트 파일 생성 (`CLAUDE.md.local`)
- Git 추적에서 제외되어 개인 정보 보호
- 작업 환경, 컴퓨터 정보, 특이사항 등 자동 기록

**예시:**
```bash
# 집에서 작업 시
./scripts/claude-guide-manager.sh local-context "집" "성능 최적화 작업"

# 회사에서 작업 시  
./scripts/claude-guide-manager.sh local-context "회사" "새 API 개발"
```

**생성되는 파일:**
- `CLAUDE.md.local` - 개인 환경별 작업 메모 (Git 제외)

## 🚨 트러블슈팅

### 문제 1: 스크립트 실행 권한 없음
```bash
# 증상
bash: ./scripts/claude-guide-manager.sh: Permission denied

# 해결
chmod +x scripts/claude-guide-manager.sh
```

### 문제 2: 워크트리 감지 실패
```bash
# 증상
🌳 워크트리 동기화를 시작합니다...
ℹ️  동기화할 워크트리가 없습니다.

# 해결
# Git 저장소 루트에서 실행 확인
pwd
ls .git

# 워크트리 존재 확인
git worktree list
```

### 문제 3: 글로벌 지침 파일 없음
```bash
# 증상
⚠️  글로벌 지침 없음: /Users/username/.claude/CLAUDE.md

# 해결
mkdir -p ~/.claude
# 글로벌 지침 파일 생성 (템플릿 제공)
```

### 문제 4: 동기화 상태 불일치
```bash
# 증상
⚠️  CLAUDE.md 동기화 필요

# 해결
./scripts/claude-guide-manager.sh sync
./scripts/claude-guide-manager.sh status  # 재확인
```

### 문제 5: rsync 명령어 없음 (macOS/Linux)
```bash
# macOS
brew install rsync

# Ubuntu/Debian
sudo apt-get install rsync

# CentOS/RHEL
sudo yum install rsync
```

### 문제 6: 로컬 컨텍스트가 Git에 포함됨
```bash
# 증상
git status
# On branch dev
# Changes to be committed:
#   new file:   CLAUDE.md.local

# 해결
git reset HEAD CLAUDE.md.local
git rm --cached CLAUDE.md.local
echo "CLAUDE.md.local" >> .gitignore
```

### 문제 7: 집-회사 동기화 충돌
```bash
# 증상
git pull
# CONFLICT (content): Merge conflict in CLAUDE.md

# 해결 방법 1: 자동 병합 수락
git add CLAUDE.md
git commit -m "merge: Claude 지침 병합"

# 해결 방법 2: 수동 병합
# 파일을 열어서 충돌 해결 후
git add CLAUDE.md
git commit -m "resolve: Claude 지침 충돌 해결"
```

### 문제 8: 로컬 컨텍스트 덮어쓰기 방지
```bash
# 증상
./scripts/claude-guide-manager.sh local-context "집" "새 작업"
# 기존 로컬 컨텍스트가 덮어써짐

# 해결
# 기존 파일 백업 후 실행
cp CLAUDE.md.local CLAUDE.md.local.backup
./scripts/claude-guide-manager.sh local-context "집" "새 작업"
```
