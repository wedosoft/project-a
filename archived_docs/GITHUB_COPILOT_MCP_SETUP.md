# GitHub Copilot 코딩 에이전트 MCP 설정 가이드

## 📋 설정 파일 사용법

### 1. MCP 설정 JSON 복사
아래 JSON을 GitHub Copilot 에이전트 설정에 붙여넣으세요:

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_TOKEN": "${env:GITHUB_TOKEN}"
      }
    },
    "filesystem": {
      "command": "npx",
      "args": [
        "@modelcontextprotocol/server-filesystem",
        "${workspaceFolder}"
      ],
      "env": {}
    },
    "project-backend": {
      "command": "npx",
      "args": [
        "@modelcontextprotocol/server-filesystem",
        "${workspaceFolder}/backend"
      ],
      "env": {}
    },
    "project-docs": {
      "command": "npx",
      "args": [
        "@modelcontextprotocol/server-filesystem",
        "${workspaceFolder}/.github"
      ],
      "env": {}
    },
    "docker": {
      "command": "python3",
      "args": ["-m", "mcp_server_docker"],
      "env": {
        "DOCKER_COMPOSE_FILE": "${workspaceFolder}/backend/docker-compose.yml"
      }
    }
  }
}
```

## 🎯 각 MCP 서버의 역할

### 1. **github** 서버
- **목적**: GitHub 이슈, PR, 코드 검색 및 관리
- **사용 예시**: 
  - "최근 이슈 확인해서 관련 코드 수정해줘"
  - "PR 리뷰 내용 반영해서 코드 개선해줘"
- **필요 권한**: Repository 읽기/쓰기 권한

### 2. **filesystem** 서버 (전체 프로젝트)
- **목적**: 프로젝트 전체 파일 시스템 접근
- **사용 예시**:
  - "프로젝트 구조 분석하고 새 기능 추가해줘"
  - "README 파일과 설정 파일들 확인해서 환경 구성해줘"

### 3. **project-backend** 서버
- **목적**: 백엔드 디렉토리 특화 접근
- **사용 예시**:
  - "FastAPI 엔드포인트 패턴 분석하고 새 API 만들어줘"
  - "LLM Router 로직 개선해줘"
  - "Qdrant 벡터 DB 연동 코드 최적화해줘"

### 4. **project-docs** 서버
- **목적**: 개발 가이드라인 및 설정 파일 접근
- **사용 예시**:
  - "프로젝트 가이드라인 확인하고 코딩 스타일 맞춰줘"
  - "CI/CD 설정 개선해줘"

### 5. **docker** 서버
- **목적**: Docker 컨테이너 관리 및 모니터링
- **사용 예시**:
  - "백엔드 컨테이너 상태 확인하고 문제 해결해줘"
  - "Docker 로그 분석해서 오류 수정해줘"

## 🔧 설치 전 준비사항

### 1. MCP 서버 설치
```bash
# GitHub Copilot 코딩 에이전트용 MCP 서버 설치
./setup_mcp_environment.sh
```

### 2. 환경변수 설정
```bash
# .env 파일에 GitHub Token 추가
echo "GITHUB_TOKEN=ghp_your_token_here" >> .env
source .env
```

### 3. GitHub Personal Access Token 생성
1. GitHub → Settings → Developer settings → Personal access tokens
2. 권한 설정:
   - Repository: Contents (Read/Write)
   - Repository: Issues (Read/Write)
   - Repository: Pull requests (Read/Write)
   - Repository: Metadata (Read)

## 🎮 사용 예시

### Copilot Chat 명령어 예시

```
@copilot GitHub에서 최근 이슈들 분석해서 우선순위 높은 버그 수정해줘

@copilot backend/api/main.py 파일 분석하고 새로운 RAG 검색 엔드포인트 추가해줘

@copilot Docker 컨테이너 상태 확인하고 성능 이슈 있으면 최적화해줘

@copilot .github/copilot-instructions.md 가이드라인 따라서 LLM Router 코드 리팩토링해줘

@copilot Freshdesk API 연동 코드에서 Rate Limit 처리 개선해줘
```

### 인라인 코드 생성 예시

```python
# TODO: Qdrant 벡터 검색 성능 최적화
# GitHub 이슈 #123의 요구사항 반영
# backend/core/vectordb.py 패턴 따르기
# 회사별 데이터 격리 유지
async def optimized_vector_search():
    # Copilot이 프로젝트 컨텍스트를 활용하여 구현
```

## 🔍 트러블슈팅

### MCP 서버 연결 실패 시
```bash
# 서버 상태 확인
npx @modelcontextprotocol/server-github --help
python3 -c "import mcp_server_docker; print('OK')"

# 권한 확인
echo $GITHUB_TOKEN
docker ps

# VS Code 재시작
# Command Palette → "Developer: Reload Window"
```

### 환경변수 인식 실패 시
```bash
# 환경변수 확인
env | grep -E "(GITHUB_TOKEN|DOCKER)"

# .env 파일 다시 로드
source .env

# VS Code 설정 확인
cat .vscode/settings.json | grep -A 10 "mcpServers"
```

## 📚 추가 참고 자료

- [MCP 설치 가이드](.github/MCP_INSTALLATION_GUIDE.md)
- [Copilot 동작 원리](.github/COPILOT_MCP_GUIDE.md)
- [프로젝트 개발 가이드라인](.github/copilot-instructions.md)

이 설정을 통해 GitHub Copilot 에이전트가 프로젝트의 전체 컨텍스트를 이해하고 더 정확한 코드 제안을 제공할 수 있습니다!
