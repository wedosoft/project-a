# GitHub Copilot 코딩 에이전트 & MCP 동작 원리

## 🤖 GitHub Copilot 코딩 에이전트란?

GitHub Copilot 코딩 에이전트는 VS Code에서 실행되는 **클라이언트 사이드 AI 어시스턴트**로, 다음과 같은 방식으로 동작합니다:

### 1. 로컬 실행 환경
- VS Code 확장으로 실행되어 **로컬 개발 환경에 직접 접근**
- 사용자의 파일 시스템, 터미널, Git 등에 직접 액세스 가능
- GitHub/Microsoft 인증을 통해 Copilot 서비스와 통신

### 2. 컨텍스트 수집 방식
```typescript
// VS Code API를 통한 프로젝트 컨텍스트 수집
const activeEditor = vscode.window.activeTextEditor;
const workspaceFiles = await vscode.workspace.findFiles('**/*.py');
const gitStatus = await vscode.extensions.getExtension('vscode.git')?.exports;
```

## 🔌 MCP (Model Context Protocol) 동작 방식

### MCP 서버 실행 환경
MCP 서버들은 **로컬 개발 환경에서 실행**되며, Copilot 에이전트가 직접 통신합니다:

```bash
# 로컬에서 실행되는 MCP 서버들
npx @modelcontextprotocol/server-github     # GitHub API 접근
npx @modelcontextprotocol/server-filesystem # 파일 시스템 접근
python -m mcp_server_docker                 # Docker 명령 실행
```

### API 키 관리 흐름

#### 1. 개발 환경 (로컬)
```bash
# 개발자의 로컬 .env 파일
GITHUB_TOKEN=ghp_your_personal_token
OPENAI_API_KEY=sk-your_openai_key
ANTHROPIC_API_KEY=sk-ant-your_key
```

#### 2. Copilot 에이전트의 API 키 접근
```typescript
// VS Code Secrets API 활용
const secrets = vscode.workspace.getConfiguration('copilot');
const githubToken = await context.secrets.get('github.token');
const openaiKey = await context.secrets.get('openai.apiKey');
```

#### 3. MCP 서버별 인증 방식

**GitHub MCP Server:**
```javascript
// 로컬 환경변수 또는 VS Code 설정에서 토큰 읽기
const token = process.env.GITHUB_TOKEN || 
              await vscode.authentication.getSession('github', ['repo']);
```

**Filesystem MCP Server:**
```python
# 로컬 파일 시스템 직접 접근 (인증 불필요)
import os
import pathlib
# 프로젝트 디렉토리 내 파일 읽기/쓰기
```

## 🏗️ 프로젝트별 설정 구조

### 현재 프로젝트 (Freshdesk Custom App) 설정

```yaml
# .github/copilot.yml
project_context:
  type: "RAG Backend Service"
  stack: "Python 3.10, FastAPI, Qdrant Cloud"
  architecture: "Microservices with LLM Router"

mcp_servers:
  - name: "github"
    auth: "GITHUB_TOKEN"
    scope: ["repo", "issues", "pull_requests"]
  
  - name: "filesystem" 
    auth: "none"
    scope: ["read", "write", "execute"]
  
  - name: "docker"
    auth: "docker_socket"
    scope: ["containers", "images", "logs"]
```

### 환경별 API 키 관리

#### 개발 환경
```bash
# .env (로컬에서만 사용)
FRESHDESK_API_KEY=your_freshdesk_key
QDRANT_API_KEY=your_qdrant_key
ANTHROPIC_API_KEY=your_anthropic_key
OPENAI_API_KEY=your_openai_key

# MCP 서버용
GITHUB_TOKEN=ghp_your_personal_token
GOOGLE_SEARCH_API_KEY=your_search_key
```

#### VS Code 설정
```json
// .vscode/settings.json
{
  "copilot.enable": true,
  "copilot.suggest.enable": true,
  "github.copilot.advanced": {
    "authProvider": "github",
    "secretsProvider": "vscode"
  }
}
```

## 🔐 보안 모델

### 1. 클라이언트 사이드 보안
- **로컬 실행**: MCP 서버가 개발자 머신에서 실행되어 네트워크 노출 최소화
- **권한 분리**: 각 MCP 서버는 필요한 최소 권한만 보유
- **토큰 관리**: VS Code Secrets API로 암호화된 저장

### 2. API 키 격리
```typescript
// 각 MCP 서버는 독립적인 인증 컨텍스트
class MCPServerManager {
  private readonly servers: Map<string, MCPServer> = new Map();
  
  async initializeServer(name: string, config: MCPConfig) {
    const credentials = await this.getCredentials(name);
    const server = new MCPServer(name, credentials);
    this.servers.set(name, server);
  }
  
  private async getCredentials(serverName: string): Promise<Credentials> {
    // VS Code Secrets API 또는 환경변수에서 안전하게 로드
    return await vscode.secrets.get(`mcp.${serverName}.credentials`);
  }
}
```

### 3. 프로덕션 배포 시 고려사항

#### GitHub Actions에서의 MCP 사용
```yaml
# .github/workflows/copilot-setup-steps.yml
env:
  # GitHub Actions Secrets 사용
  GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
  ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
  OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
  QDRANT_API_KEY: ${{ secrets.QDRANT_API_KEY }}
  FRESHDESK_API_KEY: ${{ secrets.FRESHDESK_API_KEY }}
```

#### 서버 환경 대안
```python
# backend/core/llm_router.py
class LLMRouter:
    def __init__(self):
        # 서버 환경에서는 환경변수로 직접 관리
        self.anthropic_key = os.getenv('ANTHROPIC_API_KEY')
        self.openai_key = os.getenv('OPENAI_API_KEY')
        self.gemini_key = os.getenv('GOOGLE_API_KEY')
    
    async def generate_response(self, prompt: str) -> str:
        # 운영 환경에서는 MCP 없이 직접 API 호출
        try:
            response = await self.anthropic_client.generate(prompt)
            return response
        except Exception as e:
            # 폴백 로직
            return await self.openai_client.generate(prompt)
```

## 🎯 실제 사용 시나리오

### 1. 개발 중 Copilot 에이전트 사용
```bash
# 1. MCP 서버들이 로컬에서 자동 시작
# 2. Copilot이 프로젝트 컨텍스트 분석
# 3. 개발자 요청에 따라 코드 생성/수정
```

### 2. 코드 생성 예시
```python
# 개발자: "Freshdesk 티켓 수집을 위한 새 엔드포인트 만들어줘"
# Copilot이 분석하는 컨텍스트:
# - .github/copilot-instructions.md (프로젝트 가이드라인)
# - backend/api/ (기존 API 구조)
# - backend/freshdesk/ (Freshdesk 연동 로직)
# - .env.example (필요한 환경변수)

# 생성되는 코드:
@router.post("/tickets/collect")
async def collect_tickets(
    request: CollectTicketsRequest,
    company_id: str = Depends(get_company_id)
) -> CollectTicketsResponse:
    """
    Freshdesk 티켓을 수집하여 벡터 DB에 저장
    """
    try:
        fetcher = FreshdeskFetcher()
        tickets = await fetcher.fetch_tickets_batch(
            domain=request.domain,
            api_key=request.api_key,
            batch_size=1000
        )
        
        # 벡터 임베딩 및 저장
        vectordb = QdrantVectorDB()
        await vectordb.store_tickets(tickets, company_id)
        
        return CollectTicketsResponse(
            status="success",
            collected_count=len(tickets)
        )
    except Exception as e:
        logger.error(f"티켓 수집 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

## 📋 요약

1. **GitHub Copilot 에이전트**: VS Code에서 실행되는 클라이언트 사이드 AI
2. **MCP 서버**: 로컬 환경에서 실행되어 다양한 도구/API 접근 제공
3. **API 키 관리**: VS Code Secrets API + 환경변수 조합으로 안전한 관리
4. **보안**: 로컬 실행으로 네트워크 노출 최소화, 권한 분리
5. **프로덕션**: 서버 환경에서는 MCP 없이 직접 환경변수 사용

이 구조를 통해 개발 환경에서는 강력한 AI 어시스턴트 기능을, 운영 환경에서는 안전한 API 통신을 보장할 수 있습니다.
