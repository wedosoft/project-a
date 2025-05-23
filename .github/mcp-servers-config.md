# MCP Server Configuration for Freshdesk Custom App Backend

## 권장 MCP 서버 목록

### 1. 필수 MCP 서버

#### GitHub MCP Server
- **목적**: 프로젝트 저장소 접근 및 코드 관리
- **설치**: `npm install -g @modelcontextprotocol/server-github`
- **설정**:
  ```json
  {
    "github": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "your-token"
      }
    }
  }
  ```
- **용도**: 이슈 관리, PR 생성, 코드 리뷰

#### Filesystem MCP Server
- **목적**: 로컬 파일 시스템 접근
- **설치**: `npm install -g @modelcontextprotocol/server-filesystem`
- **설정**:
  ```json
  {
    "filesystem": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-filesystem", "/Users/alan/GitHub/project-a/backend"],
      "env": {}
    }
  }
  ```
- **용도**: 코드 파일 읽기/쓰기, 로그 파일 분석

### 2. 개발 지원 MCP 서버

#### Docker MCP Server
- **목적**: Docker 컨테이너 및 서비스 관리
- **설치**: `npm install -g @modelcontextprotocol/server-docker`
- **설정**:
  ```json
  {
    "docker": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-docker"],
      "env": {}
    }
  }
  ```
- **용도**: 컨테이너 상태 확인, 로그 조회, 서비스 재시작

#### Web Search MCP Server
- **목적**: 기술 문서 및 API 레퍼런스 검색
- **설치**: `npm install -g @modelcontextprotocol/server-web-search`
- **설정**:
  ```json
  {
    "web-search": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-web-search"],
      "env": {
        "SEARCH_API_KEY": "your-key"
      }
    }
  }
  ```
- **용도**: FastAPI, Qdrant, Freshdesk API 문서 검색

### 3. 특화 MCP 서버

#### Database MCP Server (커스텀)
- **목적**: Qdrant 벡터 DB 관리
- **구현 필요**: 프로젝트별 커스텀 서버
- **기능**:
  - 컬렉션 상태 조회
  - 벡터 검색 테스트
  - 데이터 통계 확인
  
#### API Client MCP Server
- **목적**: 외부 API 테스트 및 모니터링
- **설치**: `npm install -g @modelcontextprotocol/server-api-client`
- **설정**:
  ```json
  {
    "api-client": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-api-client"],
      "env": {
        "FRESHDESK_API_KEY": "your-key",
        "OPENAI_API_KEY": "your-key",
        "ANTHROPIC_API_KEY": "your-key"
      }
    }
  }
  ```

## 설정 방법

### 1. MCP 클라이언트 설정 파일 생성

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_your_token_here"
      }
    },
    "filesystem": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-filesystem", "/Users/alan/GitHub/project-a"],
      "env": {}
    },
    "docker": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-docker"],
      "env": {}
    },
    "web-search": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-web-search"],
      "env": {
        "SEARCH_API_KEY": "your_search_api_key"
      }
    }
  }
}
```

### 2. 환경변수 설정

```bash
# GitHub 액세스
export GITHUB_PERSONAL_ACCESS_TOKEN="ghp_your_token"

# 검색 API (Google Custom Search 등)
export SEARCH_API_KEY="your_search_key"

# 프로젝트 관련 API 키들
export FRESHDESK_API_KEY="your_freshdesk_key"
export QDRANT_API_KEY="your_qdrant_key"
export OPENAI_API_KEY="your_openai_key"
```

### 3. 사용 시나리오

#### 개발 워크플로우
1. **GitHub MCP**: 이슈 생성, PR 관리
2. **Filesystem MCP**: 코드 수정, 로그 분석
3. **Docker MCP**: 서비스 상태 확인, 디버깅

#### 디버깅 워크플로우
1. **Filesystem MCP**: 로그 파일 분석
2. **Docker MCP**: 컨테이너 상태 확인
3. **API Client MCP**: 외부 API 연결 테스트

#### 문서화 워크플로우
1. **Web Search MCP**: API 문서 참조
2. **Filesystem MCP**: 문서 파일 업데이트
3. **GitHub MCP**: 변경사항 커밋

## 커스텀 MCP 서버 개발 가이드

### Qdrant 관리 MCP 서버 예시

```python
#!/usr/bin/env python3
"""
Qdrant Vector DB MCP Server
"""

import asyncio
import json
from mcp.server import Server
from mcp.types import Tool, TextContent
from qdrant_client import QdrantClient

app = Server("qdrant-manager")

@app.list_tools()
async def list_tools():
    return [
        Tool(
            name="check_collection_status",
            description="Check Qdrant collection status and point count",
            inputSchema={
                "type": "object",
                "properties": {
                    "collection_name": {"type": "string"}
                },
                "required": ["collection_name"]
            }
        ),
        Tool(
            name="search_vectors",
            description="Perform vector search in Qdrant",
            inputSchema={
                "type": "object",
                "properties": {
                    "collection_name": {"type": "string"},
                    "query_vector": {"type": "array"},
                    "limit": {"type": "integer", "default": 5}
                },
                "required": ["collection_name", "query_vector"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict):
    if name == "check_collection_status":
        # Qdrant 클라이언트 로직
        client = QdrantClient(
            url=os.getenv("QDRANT_URL"),
            api_key=os.getenv("QDRANT_API_KEY")
        )
        info = client.get_collection(arguments["collection_name"])
        return [TextContent(type="text", text=f"Points: {info.points_count}")]
    
    # 다른 도구들...

if __name__ == "__main__":
    asyncio.run(app.run())
```

## 설치 및 실행 스크립트

```bash
#!/bin/bash
# setup_mcp_servers.sh

echo "Installing MCP servers for Freshdesk Custom App Backend..."

# 필수 서버 설치
npm install -g @modelcontextprotocol/server-github
npm install -g @modelcontextprotocol/server-filesystem
npm install -g @modelcontextprotocol/server-docker
npm install -g @modelcontextprotocol/server-web-search

echo "MCP servers installation completed!"
echo "Please configure your MCP client with the provided JSON configuration."
```

이러한 MCP 서버 구성을 통해 GitHub Copilot 에이전트가 프로젝트의 전체 컨텍스트를 이해하고 효과적으로 개발 작업을 수행할 수 있습니다.
