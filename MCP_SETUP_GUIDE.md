# Claude Code MCP 서버 설정 가이드

## 🚀 빠른 설치

```bash
# 실행 권한 부여
chmod +x setup-mcp-servers.sh

# MCP 서버 설치 실행
./setup-mcp-servers.sh
```

## 📋 설치된 서버 목록

### 필수 개발 도구
- **filesystem-server**: 프로젝트 파일 시스템 접근
- **git-server**: Git 저장소 관리 및 버전 제어
- **memory-server**: Claude의 컨텍스트 기억 기능

### 데이터베이스
- **sqlite-server**: 로컬 SQLite 데이터베이스 접근
- **postgres-server**: PostgreSQL 데이터베이스 연결

### 외부 서비스
- **github-server**: GitHub API 접근 (이슈, PR 관리)
- **brave-search**: 웹 검색 기능
- **puppeteer-server**: 웹 스크래핑 및 자동화

## 🔐 인증 설정

1. `.env.example`을 `.env`로 복사
2. 필요한 API 키들을 설정
3. Claude Code에서 `/mcp` 명령어로 원격 서버 인증

## 🛠️ 사용법

### 파일 시스템 접근
```
@filesystem-server:file://src/components/Button.tsx
```

### Git 작업
```
/mcp__git__commit "feat: 새로운 기능 추가"
```

### 데이터베이스 쿼리
```
@postgres-server:schema://users
```

### GitHub 작업
```
/mcp__github__create_issue "버그 수정" "로그인 오류 발생"
```

## 🔧 문제 해결

- 서버 상태 확인: `claude mcp list`
- 인증 상태 확인: Claude Code에서 `/mcp`
- 서버 재시작: `claude mcp remove <server-name>` 후 재설치
