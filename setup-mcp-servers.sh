#!/bin/bash

echo "🚀 Claude Code MCP 서버 설치를 시작합니다..."

# 1. 파일시스템 MCP 서버 (로컬 파일 접근)
echo "📁 파일시스템 서버 설치 중..."
claude mcp add filesystem-server -s project npx @modelcontextprotocol/server-filesystem /Users/alan/GitHub/project-a

# 2. Git MCP 서버 (Git 저장소 관리)
echo "🔧 Git 서버 설치 중..."
claude mcp add git-server -s project npx @modelcontextprotocol/server-git

# 3. SQLite MCP 서버 (로컬 데이터베이스)
echo "🗄️ SQLite 서버 설치 중..."
claude mcp add sqlite-server -s project npx @modelcontextprotocol/server-sqlite

# 4. PostgreSQL MCP 서버 (만약 PostgreSQL을 사용한다면)
echo "🐘 PostgreSQL 서버 설치 중..."
claude mcp add postgres-server -s project npx @modelcontextprotocol/server-postgres \
  -e DATABASE_URL="postgresql://localhost:5432/project_a"

# 5. Brave Search MCP 서버 (웹 검색)
echo "🔍 Brave Search 서버 설치 중..."
claude mcp add brave-search -s project npx @modelcontextprotocol/server-brave-search \
  -e BRAVE_API_KEY="${BRAVE_API_KEY:-your-brave-api-key}"

# 6. GitHub MCP 서버 (GitHub API 접근)
echo "🐙 GitHub 서버 설치 중..."
claude mcp add github-server -s project npx @modelcontextprotocol/server-github \
  -e GITHUB_PERSONAL_ACCESS_TOKEN="${GITHUB_TOKEN:-your-github-token}"

# 7. Puppeteer MCP 서버 (웹 스크래핑)
echo "🤖 Puppeteer 서버 설치 중..."
claude mcp add puppeteer-server -s project npx @modelcontextprotocol/server-puppeteer

# 8. Memory MCP 서버 (컨텍스트 기억)
echo "🧠 Memory 서버 설치 중..."
claude mcp add memory-server -s project npx @modelcontextprotocol/server-memory

echo "✅ MCP 서버 설치 완료!"
echo "📋 설치된 서버 목록을 확인하려면: claude mcp list"
echo "🔐 인증이 필요한 서버는 Claude Code에서 /mcp 명령어로 인증해주세요"
