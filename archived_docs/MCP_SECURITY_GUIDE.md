# MCP Server 환경변수 설정 가이드

## 🔐 MCP 서버별 API 키 관리

### ✅ 안전한 서버 (API 키 불필요)
- **Filesystem MCP Server**: 로컬 파일 접근만
- **Docker MCP Server**: 로컬 Docker 데몬 접근만
- **System MCP Server**: 시스템 명령어 실행만

### ⚠️ API 키 필요한 서버

#### 1. GitHub MCP Server
```bash
# GitHub Personal Access Token 생성 필요
# GitHub → Settings → Developer settings → Personal access tokens
GITHUB_PERSONAL_ACCESS_TOKEN=ghp_your_token_here
```
**권한 범위**: repo, issues, pull_requests

#### 2. Web Search MCP Server
```bash
# Google Custom Search API 또는 Bing Search API
GOOGLE_SEARCH_API_KEY=your_google_api_key
GOOGLE_SEARCH_ENGINE_ID=your_search_engine_id
```

#### 3. API Client MCP Server
```bash
# 기존 환경변수 재사용 가능
FRESHDESK_API_KEY=your_freshdesk_key
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
```

## 🔧 VS Code MCP 설정 파일

VS Code의 `settings.json`에서 MCP 서버 설정:

```json
{
  "mcp.servers": {
    "filesystem": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-filesystem", "/Users/alan/GitHub/project-a"],
      "env": {}
    },
    "github": {
      "command": "npx", 
      "args": ["@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "${env:GITHUB_PERSONAL_ACCESS_TOKEN}"
      }
    },
    "docker": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-docker"],
      "env": {}
    }
  }
}
```

## 🛡️ 보안 원칙

### ❌ 하면 안 되는 것
- MCP 설정 파일에 실제 API 키 하드코딩
- GitHub에 MCP 설정 파일과 API 키 함께 업로드
- 불필요한 권한의 API 키 사용

### ✅ 해야 하는 것
- 환경변수 참조 사용: `"${env:VARIABLE_NAME}"`
- 최소 권한 원칙으로 API 키 생성
- 정기적인 API 키 교체
- 로컬 환경변수 파일로 관리

## 📝 환경변수 업데이트

기존 `.env.example`에 MCP 관련 환경변수 추가:

```bash
# =================================================================
# MCP Server API Keys (선택사항)
# =================================================================
GITHUB_PERSONAL_ACCESS_TOKEN=ghp_your_token_here
GOOGLE_SEARCH_API_KEY=your_google_search_key
GOOGLE_SEARCH_ENGINE_ID=your_search_engine_id
```

## 🔄 안전한 설정 순서

1. **환경변수 설정**:
   ```bash
   # .env 파일에 추가
   echo "GITHUB_PERSONAL_ACCESS_TOKEN=your_token" >> .env
   ```

2. **VS Code 설정**:
   ```json
   // settings.json에서 환경변수 참조
   "env": {
     "GITHUB_PERSONAL_ACCESS_TOKEN": "${env:GITHUB_PERSONAL_ACCESS_TOKEN}"
   }
   ```

3. **검증**:
   ```bash
   # 환경변수 로드 확인
   source .env && echo $GITHUB_PERSONAL_ACCESS_TOKEN
   ```

## 🆘 문제 해결

### "Token not found" 에러
- 환경변수가 제대로 로드되었는지 확인
- VS Code 재시작 후 다시 시도
- 토큰 권한 확인

### "Invalid token" 에러  
- GitHub Personal Access Token 만료 확인
- 필요한 권한(repo, issues) 설정 확인
- 새 토큰 생성 후 교체
