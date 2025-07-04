#!/bin/bash

# 🌳 Copilot Canvas 워크트리 설정 스크립트
# 개발 속도 향상을 위한 특화된 워크트리 분리

set -e

echo "🚀 Copilot Canvas 워크트리 설정을 시작합니다..."

# 현재 위치 확인
if [ ! -d ".git" ]; then
    echo "❌ 에러: Git 저장소 루트에서 실행해주세요."
    exit 1
fi

PROJECT_ROOT=$(pwd)
PARENT_DIR=$(dirname "$PROJECT_ROOT")
PROJECT_NAME=$(basename "$PROJECT_ROOT")

echo "📂 프로젝트 루트: $PROJECT_ROOT"
echo "📁 부모 디렉토리: $PARENT_DIR"

# 브랜치 생성 함수
create_branch_if_not_exists() {
    local branch_name=$1
    
    if git show-ref --verify --quiet refs/heads/$branch_name; then
        echo "✅ 브랜치 '$branch_name'가 이미 존재합니다."
    else
        echo "🌿 브랜치 '$branch_name'를 생성합니다..."
        git checkout -b $branch_name
        git checkout main  # 메인 브랜치로 돌아가기
    fi
}

# 워크트리 생성 함수
create_worktree() {
    local branch_name=$1
    local worktree_path=$2
    local description=$3
    
    echo ""
    echo "🔧 $description 워크트리 생성 중..."
    echo "   브랜치: $branch_name"
    echo "   경로: $worktree_path"
    
    if [ -d "$worktree_path" ]; then
        echo "⚠️  워크트리가 이미 존재합니다: $worktree_path"
        return
    fi
    
    # 브랜치 생성
    create_branch_if_not_exists $branch_name
    
    # 워크트리 생성
    git worktree add "$worktree_path" $branch_name
    
    echo "✅ $description 워크트리 생성 완료!"
}

# 메인 브랜치로 체크아웃
echo "🔄 메인 브랜치로 이동합니다..."
git checkout main

# 워크트리들 생성
echo ""
echo "🌳 워크트리들을 생성합니다..."

create_worktree "worktree/api-core" \
    "$PARENT_DIR/${PROJECT_NAME}-api-core" \
    "Backend API & Core"

create_worktree "worktree/vector-search" \
    "$PARENT_DIR/${PROJECT_NAME}-vector-search" \
    "Vector DB & Search"

create_worktree "worktree/llm-management" \
    "$PARENT_DIR/${PROJECT_NAME}-llm-management" \
    "LLM Management"

create_worktree "worktree/data-pipeline" \
    "$PARENT_DIR/${PROJECT_NAME}-data-pipeline" \
    "Data Pipeline & Ingestion"

create_worktree "worktree/database-orm" \
    "$PARENT_DIR/${PROJECT_NAME}-database-orm" \
    "Database & ORM"

create_worktree "worktree/frontend" \
    "$PARENT_DIR/${PROJECT_NAME}-frontend" \
    "Frontend FDK"

# 워크트리 상태 확인
echo ""
echo "📋 생성된 워크트리 목록:"
git worktree list

# VS Code 멀티 루트 작업영역 파일 생성
echo ""
echo "🛠️  VS Code 멀티 루트 작업영역 파일을 생성합니다..."

WORKSPACE_FILE="$PROJECT_ROOT/copilot-canvas-worktrees.code-workspace"

cat > "$WORKSPACE_FILE" << 'EOF'
{
    "folders": [
        {
            "name": "🏠 Main Project",
            "path": "."
        },
        {
            "name": "🚀 API & Core",
            "path": "../project-a-api-core"
        },
        {
            "name": "🔍 Vector Search", 
            "path": "../project-a-vector-search"
        },
        {
            "name": "🧠 LLM Management",
            "path": "../project-a-llm-management"
        },
        {
            "name": "📊 Data Pipeline",
            "path": "../project-a-data-pipeline"
        },
        {
            "name": "💾 Database & ORM",
            "path": "../project-a-database-orm"
        },
        {
            "name": "🎨 Frontend FDK",
            "path": "../project-a-frontend"
        }
    ],
    "settings": {
        "python.defaultInterpreterPath": "./backend/venv/bin/python",
        "python.terminal.activateEnvironment": true,
        "files.exclude": {
            "**/__pycache__": true,
            "**/.pytest_cache": true,
            "**/node_modules": true,
            "**/.git": false
        },
        "search.exclude": {
            "**/node_modules": true,
            "**/venv": true,
            "**/__pycache__": true
        },
        "git.openRepositoryInParentFolders": "always",
        "git.detectSubmodules": false
    },
    "extensions": {
        "recommendations": [
            "ms-python.python",
            "ms-python.vscode-pylance", 
            "bradlc.vscode-tailwindcss",
            "ms-vscode.vscode-json",
            "redhat.vscode-yaml",
            "ms-vscode.git-lens",
            "github.copilot",
            "github.copilot-chat"
        ]
    },
    "tasks": {
        "version": "2.0.0",
        "tasks": [
            {
                "label": "🚀 Start Backend Development",
                "type": "shell",
                "command": "cd backend && source venv/bin/activate && python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000",
                "group": "build",
                "isBackground": true,
                "presentation": {
                    "echo": true,
                    "reveal": "always",
                    "focus": false,
                    "panel": "shared"
                }
            },
            {
                "label": "🎨 Start Frontend Development", 
                "type": "shell",
                "command": "cd frontend && fdk run",
                "group": "build",
                "isBackground": true,
                "presentation": {
                    "echo": true,
                    "reveal": "always",
                    "focus": false,
                    "panel": "shared"
                }
            },
            {
                "label": "🔍 Test Vector Search",
                "type": "shell",
                "command": "cd backend && source venv/bin/activate && python -c \"from core.database.vectordb import vector_db; print('✅ Vector DB OK')\"",
                "group": "test"
            },
            {
                "label": "🧠 Test LLM Manager",
                "type": "shell", 
                "command": "cd backend && source venv/bin/activate && python -c \"from core.llm.manager import LLMManager; print('✅ LLM Manager OK')\"",
                "group": "test"
            }
        ]
    }
}
EOF

echo "✅ VS Code 작업영역 파일 생성 완료: $WORKSPACE_FILE"

# 사용법 안내
echo ""
echo "🎉 워크트리 설정이 완료되었습니다!"
echo ""
echo "📋 다음 단계:"
echo "1. VS Code에서 다음 파일을 열어주세요:"
echo "   File → Open Workspace → copilot-canvas-worktrees.code-workspace"
echo ""
echo "2. 또는 터미널에서 바로 열기:"
echo "   code copilot-canvas-worktrees.code-workspace"
echo ""
echo "3. 각 워크트리별 CLAUDE.md 파일들이 생성되어 있습니다:"
echo "   - backend/api/CLAUDE.md (API & Core)"
echo "   - backend/core/search/CLAUDE.md (Vector Search)"
echo "   - backend/core/llm/CLAUDE.md (LLM Management)"
echo "   - backend/core/ingest/CLAUDE.md (Data Pipeline)"
echo "   - backend/core/database/CLAUDE.md (Database & ORM)"
echo "   - frontend/CLAUDE.md (Frontend FDK)"
echo ""
echo "💡 팁:"
echo "   - Ctrl+Shift+P → 'Git: Switch Branch' 로 워크트리 간 브랜치 전환"
echo "   - Ctrl+P 로 모든 워크트리의 파일에 빠르게 접근"
echo "   - 하단 터미널에서 각 워크트리별 작업 가능"
echo ""
echo "🔄 워크트리 제거가 필요한 경우:"
echo "   git worktree remove <path>"
echo "   git branch -d <branch-name>"
