# MCP 서버 설치 및 설정 가이드

## 🚀 MCP 서버 자동 설치 스크립트

### 전체 설치 스크립트
```bash
#!/bin/bash
# install_mcp_servers.sh

echo "🔧 MCP 서버 설치 시작..."

# Node.js 기반 MCP 서버들
echo "📦 GitHub MCP Server 설치..."
npm install -g @modelcontextprotocol/server-github

echo "📁 Filesystem MCP Server 설치..."
npm install -g @modelcontextprotocol/server-filesystem

echo "🔍 Web Search MCP Server 설치..."
npm install -g @modelcontextprotocol/server-web-search

# Python 기반 MCP 서버들
echo "🐳 Docker MCP Server 설치..."
pip install mcp-server-docker

echo "🗄️ SQLite MCP Server 설치..."
pip install mcp-server-sqlite

echo "✅ MCP 서버 설치 완료!"

# 설치 확인
echo "🔍 설치된 MCP 서버 확인..."
npx @modelcontextprotocol/server-github --version
npx @modelcontextprotocol/server-filesystem --version
python -c "import mcp_server_docker; print('Docker MCP Server: OK')"

echo "🎉 모든 MCP 서버가 성공적으로 설치되었습니다!"
```

### VS Code MCP 설정 파일
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
      "args": ["@modelcontextprotocol/server-filesystem", "${workspaceFolder}"],
      "env": {}
    },
    "docker": {
      "command": "python",
      "args": ["-m", "mcp_server_docker"],
      "env": {}
    },
    "web-search": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-web-search"],
      "env": {
        "GOOGLE_SEARCH_API_KEY": "${env:GOOGLE_SEARCH_API_KEY}",
        "GOOGLE_SEARCH_ENGINE_ID": "${env:GOOGLE_SEARCH_ENGINE_ID}"
      }
    }
  }
}
```

## 🔑 API 키 설정

### 1. GitHub Personal Access Token
```bash
# GitHub Settings → Developer settings → Personal access tokens → Fine-grained tokens
# 권한: Repository access (All repositories or Selected repositories)
# Repository permissions:
# - Contents: Read and write
# - Issues: Read and write  
# - Pull requests: Read and write
# - Metadata: Read

export GITHUB_TOKEN="ghp_your_token_here"
```

### 2. Google Search API 설정
```bash
# Google Cloud Console → APIs & Services → Credentials
# 1. API 키 생성
# 2. Custom Search JSON API 활성화
# 3. Programmable Search Engine 생성

export GOOGLE_SEARCH_API_KEY="your_api_key"
export GOOGLE_SEARCH_ENGINE_ID="your_engine_id"
```

### 3. VS Code Secrets 설정
```typescript
// Command Palette → "Preferences: Open User Settings (JSON)"
{
  "github.copilot.advanced": {
    "authProvider": "github"
  },
  "mcp.servers.github.env.GITHUB_TOKEN": "${secret:github.token}",
  "mcp.servers.webSearch.env.GOOGLE_SEARCH_API_KEY": "${secret:google.search.apiKey}"
}
```

## 🧪 MCP 서버 테스트

### 테스트 스크립트
```bash
#!/bin/bash
# test_mcp_servers.sh

echo "🧪 MCP 서버 연결 테스트 시작..."

# GitHub MCP Server 테스트
echo "🐙 GitHub MCP Server 테스트..."
timeout 10s npx @modelcontextprotocol/server-github --test || echo "❌ GitHub MCP 실패"

# Filesystem MCP Server 테스트  
echo "📁 Filesystem MCP Server 테스트..."
timeout 10s npx @modelcontextprotocol/server-filesystem /tmp --test || echo "❌ Filesystem MCP 실패"

# Docker MCP Server 테스트
echo "🐳 Docker MCP Server 테스트..."
timeout 10s python -c "
import mcp_server_docker
print('✅ Docker MCP Server: 연결 성공')
" || echo "❌ Docker MCP 실패"

echo "✅ MCP 서버 테스트 완료!"
```

## 🛠️ 프로젝트별 MCP 구성

### Freshdesk Custom App 전용 설정
```json
{
  "mcpServers": {
    "project-filesystem": {
      "command": "npx",
      "args": [
        "@modelcontextprotocol/server-filesystem", 
        "${workspaceFolder}/backend",
        "${workspaceFolder}/.github",
        "${workspaceFolder}/docs"
      ],
      "env": {}
    },
    "project-github": {
      "command": "npx", 
      "args": ["@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_TOKEN": "${env:GITHUB_TOKEN}",
        "GITHUB_REPOSITORY": "alan-ai/project-a"
      }
    },
    "docker-backend": {
      "command": "python",
      "args": ["-m", "mcp_server_docker"],
      "env": {
        "DOCKER_COMPOSE_FILE": "${workspaceFolder}/docker-compose.yml"
      }
    }
  }
}
```

## 🔧 고급 설정

### 1. MCP 서버 로깅
```bash
# 로그 디렉토리 생성
mkdir -p ~/.vscode/mcp-logs

# 환경변수 설정
export MCP_LOG_LEVEL=debug
export MCP_LOG_DIR=~/.vscode/mcp-logs
```

### 2. 커스텀 MCP 서버 (선택사항)
```python
# custom_mcp_server.py - Freshdesk API 전용 MCP 서버
import asyncio
from mcp import MCPServer
from freshdesk_api import FreshdeskAPI

class FreshdeskMCPServer(MCPServer):
    def __init__(self):
        super().__init__("freshdesk")
        self.freshdesk = FreshdeskAPI()
    
    async def get_tickets(self, domain: str, api_key: str):
        """Freshdesk 티켓 조회"""
        return await self.freshdesk.get_tickets(domain, api_key)
    
    async def get_knowledge_base(self, domain: str, api_key: str):
        """Freshdesk 지식베이스 조회"""
        return await self.freshdesk.get_articles(domain, api_key)

if __name__ == "__main__":
    server = FreshdeskMCPServer()
    asyncio.run(server.start())
```

### 3. VS Code Extension 설정
```json
{
  "extensions.recommendations": [
    "github.copilot",
    "github.copilot-chat", 
    "ms-python.python",
    "ms-python.flake8",
    "ms-python.black-formatter",
    "bradlc.vscode-tailwindcss"
  ],
  "mcp.autoStart": true,
  "mcp.timeout": 30000,
  "mcp.retryAttempts": 3
}
```

## 📋 트러블슈팅

### 일반적인 문제 해결

#### 1. Node.js MCP 서버 실행 실패
```bash
# Node.js 버전 확인
node --version  # 18+ 필요

# 글로벌 설치 경로 확인
npm config get prefix
npm list -g --depth=0

# 권한 문제 해결
sudo chown -R $(whoami) $(npm config get prefix)/{lib/node_modules,bin,share}
```

#### 2. Python MCP 서버 실행 실패
```bash
# Python 가상환경 사용 권장
python -m venv mcp-env
source mcp-env/bin/activate
pip install mcp-server-docker mcp-server-sqlite

# 가상환경 경로를 VS Code 설정에 반영
```

#### 3. API 키 인식 실패
```bash
# 환경변수 확인
echo $GITHUB_TOKEN
echo $GOOGLE_SEARCH_API_KEY

# VS Code 재시작
# Command Palette → "Developer: Reload Window"
```

#### 4. Docker MCP 서버 권한 문제
```bash
# Docker 소켓 권한 확인
ls -la /var/run/docker.sock

# 사용자를 docker 그룹에 추가
sudo usermod -aG docker $USER
newgrp docker
```

## 🎯 사용 방법

### 1. Copilot Chat에서 MCP 활용
```
@copilot GitHub에서 최근 이슈들을 확인해서 버그 리포트 분석해줘

@copilot backend/api/ 폴더의 모든 파일을 읽고 새로운 엔드포인트 패턴 제안해줘

@copilot Docker 컨테이너 상태 확인하고 문제 있으면 수정해줘
```

### 2. 인라인 코드 생성
```python
# 주석으로 의도 설명하면 Copilot이 MCP를 활용하여 컨텍스트 반영
# TODO: Freshdesk API에서 티켓을 가져와서 Qdrant에 저장하는 함수 만들기
# GitHub 이슈 #123의 요구사항 반영
# 기존 backend/freshdesk/fetcher.py 패턴 따르기
```

### 3. 코드 리뷰 및 개선
```
@copilot 이 코드를 리뷰하고 보안 취약점이나 성능 개선점 찾아줘. GitHub의 베스트 프랙티스와 비교해서 제안해줘.
```

이제 MCP 서버들이 설치되면 GitHub Copilot이 프로젝트의 전체 컨텍스트를 활용하여 더 정확하고 유용한 코드 제안을 제공할 수 있습니다!
