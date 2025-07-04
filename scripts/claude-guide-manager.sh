#!/bin/bash

# Claude 지침 관리 스크립트 v2.0
# 사용법: ./scripts/claude-guide-manager.sh [command] [options]

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GLOBAL_CLAUDE="$HOME/.claude/CLAUDE.md"
PROJECT_CLAUDE="$PROJECT_ROOT/CLAUDE.md"
PROJECT_CLAUDE_DIR="$PROJECT_ROOT/.claude"
CLAUDE_FILES=()

# 지침 구조 초기화 및 정리
init_structure() {
    echo "🏗️ Claude 지침 구조를 초기화합니다..."
    
    # 1. 프로젝트 .claude 디렉토리 생성
    mkdir -p "$PROJECT_CLAUDE_DIR/modules"
    
    # 2. 기존 CLAUDE.md 파일들을 통합
    consolidate_guides
    
    # 3. 중복 제거
    cleanup_duplicates
    
    echo "✅ Claude 지침 구조가 정리되었습니다."
}

# 기존 가이드들을 통합
consolidate_guides() {
    echo "📦 기존 CLAUDE.md 파일들을 통합 중..."
    
    # 백엔드 관련 파일들을 하나로 통합
    cat > "$PROJECT_CLAUDE_DIR/backend-guide.md" << 'EOF'
# 백엔드 개발 가이드

## 🎯 프로젝트 컨텍스트
- RAG 기반 Freshdesk Custom App 백엔드
- FastAPI + Qdrant + 멀티 LLM 아키텍처
- 성능 최적화 및 멀티테넌트 지원

## 🏗️ 아키텍처 패턴
- 의존성 주입 (IoC Container)
- 비동기 처리 우선
- 멀티테넌트 데이터 격리

## 🔧 개발 지침
- Python 3.10+ async/await 패턴
- 타입 힌팅 필수
- Pydantic 모델 활용
- 구조화된 로깅

## 📊 성능 고려사항
- DB 쿼리 최적화 (N+1 방지)
- 벡터 검색 최적화
- 메모리 효율적 처리
- 캐싱 전략 적용

EOF

    # 프론트엔드 가이드 생성
    if [[ -f "$PROJECT_ROOT/frontend/CLAUDE.md" ]]; then
        mv "$PROJECT_ROOT/frontend/CLAUDE.md" "$PROJECT_CLAUDE_DIR/frontend-guide.md"
    fi
    
    # 모듈별 전문 지침들 이동
    for module in database llm search ingest; do
        if [[ -f "$PROJECT_ROOT/backend/core/$module/CLAUDE.md" ]]; then
            echo "  📦 $module 모듈 가이드 이동 중..."
            mv "$PROJECT_ROOT/backend/core/$module/CLAUDE.md" "$PROJECT_CLAUDE_DIR/modules/$module.md"
        fi
    done
}

# 중복 파일 정리
cleanup_duplicates() {
    echo "🧹 중복 CLAUDE.md 파일들을 정리 중..."
    
    # 백업 생성
    if [[ -f "$PROJECT_CLAUDE" ]]; then
        cp "$PROJECT_CLAUDE" "$PROJECT_CLAUDE.backup.$(date +%Y%m%d)"
    fi
    
    # 하위 디렉토리의 CLAUDE.md 파일들 제거 (백업 후)
    find "$PROJECT_ROOT" -name "CLAUDE.md" -not -path "$PROJECT_CLAUDE" | while read -r file; do
        backup_file="${file}.backup.$(date +%Y%m%d)"
        echo "  🗃️  백업: $file → $backup_file"
        mv "$file" "$backup_file"
    done
}

# 간소화된 프로젝트 CLAUDE.md 생성
create_simplified_project_guide() {
    echo "📝 간소화된 프로젝트 CLAUDE.md를 생성합니다..."
    
    cat > "$PROJECT_CLAUDE" << 'EOF'
# 프로젝트 컨텍스트 & 현재 작업

> 이 파일은 **현재 작업 컨텍스트**에만 집중합니다.
> 상세 가이드라인은 `.claude/` 폴더를 참조하세요.

## 🎯 프로젝트 개요
RAG 기반 Freshdesk Custom App - FastAPI + Qdrant + 멀티 LLM

## 🔄 현재 작업 컨텍스트 (2025-07-04)
- **작업**: Claude 지침 구조 최적화
- **목표**: 지침 관리 간소화 및 일관성 확보
- **범위**: 전체 프로젝트 문서 구조
- **상태**: 진행 중

## 📂 상세 지침 위치
- **백엔드**: `.claude/backend-guide.md`
- **프론트엔드**: `.claude/frontend-guide.md`
- **모듈별**: `.claude/modules/[module].md`
- **글로벌 원칙**: `~/.claude/CLAUDE.md`

## ⚡ 빠른 참조
```bash
# 지침 관리 도구
./scripts/claude-guide-manager.sh

# 구조 확인
./scripts/claude-guide-manager.sh hierarchy

# 현재 컨텍스트 확인
./scripts/claude-guide-manager.sh context
```

---
**💡 팁**: Claude Code 사용 시 이 파일을 먼저 읽고, 필요에 따라 `.claude/` 폴더의 상세 가이드를 참조하세요.
EOF

    echo "✅ 간소화된 프로젝트 CLAUDE.md가 생성되었습니다."
}

# 새로운 지침 구조 표시
show_new_structure() {
    echo ""
    echo "🏗️ 새로운 Claude 지침 구조:"
    echo ""
    
    # 글로벌 지침 확인
    if [[ -f "$GLOBAL_CLAUDE" ]]; then
        echo "🌍 글로벌 원칙: $GLOBAL_CLAUDE"
    else
        echo "⚠️  글로벌 지침 없음: $GLOBAL_CLAUDE"
    fi
    
    echo ""
    echo "🏠 프로젝트 지침:"
    echo "  📄 메인: CLAUDE.md (현재 작업 컨텍스트만)"
    echo ""
    echo "📁 상세 가이드 (.claude/):"
    
    if [[ -f "$PROJECT_CLAUDE_DIR/backend-guide.md" ]]; then
        echo "  🔧 백엔드: .claude/backend-guide.md"
    fi
    
    if [[ -f "$PROJECT_CLAUDE_DIR/frontend-guide.md" ]]; then
        echo "  � 프론트엔드: .claude/frontend-guide.md"
    fi
    
    if [[ -d "$PROJECT_CLAUDE_DIR/modules" ]]; then
        echo "  � 모듈별 가이드:"
        for module_file in "$PROJECT_CLAUDE_DIR/modules"/*.md; do
            if [[ -f "$module_file" ]]; then
                module_name=$(basename "$module_file" .md)
                echo "    • $module_name: .claude/modules/$module_name.md"
            fi
        done
    fi
}

# Claude Code 최적화 가이드 표시
show_optimization_guide() {
    echo ""
    echo "🚀 Claude Code 최적화 가이드:"
    echo ""
    echo "1. 📂 파일 참조 순서:"
    echo "   - 현재 작업: CLAUDE.md (프로젝트 루트)"
    echo "   - 상세 지침: .claude/backend-guide.md 또는 frontend-guide.md"
    echo "   - 모듈 전문: .claude/modules/[모듈명].md"
    echo "   - 글로벌 원칙: ~/.claude/CLAUDE.md"
    echo ""
    echo "2. 🎯 Claude Code 사용 팁:"
    echo "   - 작업 시작 시: '현재 CLAUDE.md 컨텍스트를 확인해주세요'"
    echo "   - 모듈 작업 시: '.claude/modules/database.md 가이드라인을 따라주세요'"
    echo "   - 성능 최적화: '.claude/backend-guide.md의 성능 섹션을 참조해주세요'"
    echo ""
    echo "3. 📝 컨텍스트 업데이트:"
    echo "   ./scripts/claude-guide-manager.sh update-context '새 작업 설명'"
    echo ""
    echo "4. 🔍 구조 확인:"
    echo "   ./scripts/claude-guide-manager.sh structure"
}

# 컨텍스트 기반 가이드 추천
recommend_guide() {
    local work_type="$1"
    
    echo ""
    echo "💡 작업 유형별 가이드 추천:"
    echo ""
    
    case "$work_type" in
        "performance"|"성능")
            echo "🚀 성능 최적화 작업:"
            echo "  1. CLAUDE.md - 현재 성능 목표 확인"
            echo "  2. .claude/backend-guide.md - 성능 최적화 패턴"
            echo "  3. .claude/modules/database.md - DB 쿼리 최적화"
            ;;
        "api"|"엔드포인트")
            echo "🔗 API 개발 작업:"
            echo "  1. CLAUDE.md - 프로젝트 컨텍스트"
            echo "  2. .claude/backend-guide.md - API 패턴"
            echo "  3. ~/.claude/CLAUDE.md - 보안 원칙"
            ;;
        "frontend"|"프론트엔드")
            echo "🎨 프론트엔드 작업:"
            echo "  1. .claude/frontend-guide.md - FDK 가이드라인"
            echo "  2. ~/.claude/CLAUDE.md - JavaScript 컨벤션"
            ;;
        *)
            echo "🎯 일반 개발 작업:"
            echo "  1. CLAUDE.md - 현재 작업 컨텍스트"
            echo "  2. 해당 영역의 .claude/ 가이드"
            echo "  3. ~/.claude/CLAUDE.md - 글로벌 원칙"
            ;;
    esac
}

# 지침 일관성 검사
check_consistency() {
    echo ""
    echo "🔍 지침 일관성 검사:"
    echo ""
    
    local issues=0
    
    # 1. 모든 백엔드 모듈에 CLAUDE.md가 있는지 확인
    find "$PROJECT_ROOT/backend/core" -maxdepth 1 -type d | while read -r dir; do
        if [[ -d "$dir" && ! -f "$dir/CLAUDE.md" ]]; then
            module_name=$(basename "$dir")
            if [[ "$module_name" != "core" ]]; then
                echo "⚠️  누락: $dir/CLAUDE.md"
                ((issues++))
            fi
        fi
    done
    
    # 2. CLAUDE.md 파일들의 기본 구조 확인
    for file in "${CLAUDE_FILES[@]}"; do
        if ! grep -q "컨텍스트\|Context" "$file"; then
            echo "⚠️  컨텍스트 섹션 누락: $file"
            ((issues++))
        fi
        
        if ! grep -q "구조\|Structure" "$file"; then
            echo "⚠️  구조 섹션 누락: $file"
            ((issues++))
        fi
    done
    
    if [[ $issues -eq 0 ]]; then
        echo "✅ 모든 지침이 일관성 있게 구성되어 있습니다."
    else
        echo "❌ $issues개의 일관성 문제가 발견되었습니다."
    fi
}

# 작업 컨텍스트 업데이트
update_context() {
    local context_desc="$1"
    local priority="$2"
    local scope="$3"
    
    if [[ -z "$context_desc" ]]; then
        echo "사용법: $0 update-context '작업 설명' [우선순위] [범위]"
        exit 1
    fi
    
    local context_section="## 🔄 현재 작업 컨텍스트 ($(date +%Y-%m-%d))
- **작업**: $context_desc
- **우선순위**: ${priority:-중간}
- **범위**: ${scope:-backend 최적화}
- **시작일**: $(date +%Y-%m-%d)
- **상태**: 진행 중

"
    
    # 프로젝트 루트 CLAUDE.md 업데이트
    if [[ -f "$PROJECT_ROOT/CLAUDE.md" ]]; then
        # 기존 작업 컨텍스트 제거하고 새로 추가
        sed -i.bak '/## 🔄 현재 작업 컨텍스트/,/^## /{ /^## 🔄 현재 작업 컨텍스트/d; /^## /!d; }' "$PROJECT_ROOT/CLAUDE.md"
        
        # 파일 상단에 새 컨텍스트 추가
        echo -e "$context_section$(cat "$PROJECT_ROOT/CLAUDE.md")" > "$PROJECT_ROOT/CLAUDE.md"
        
        echo "✅ 작업 컨텍스트가 업데이트되었습니다."
    else
        echo "⚠️  프로젝트 루트 CLAUDE.md 파일이 없습니다."
    fi
}

# 로컬 컨텍스트 관리 (집-회사 동기화용)
create_local_context() {
    local location="$1"
    local context_desc="$2"
    
    if [[ -z "$location" ]]; then
        echo "사용법: $0 local-context [집|회사] '작업 설명'"
        exit 1
    fi
    
    local local_claude="$PROJECT_ROOT/CLAUDE.md.local"
    
    cat > "$local_claude" << EOF
# 로컬 작업 컨텍스트 (Git 추적 제외)

## 🏠 작업 환경
- **위치**: $location
- **작업자**: $(whoami)
- **컴퓨터**: $(hostname)
- **날짜**: $(date +%Y-%m-%d)

## 🔄 현재 로컬 작업
- **작업**: ${context_desc:-"개발 작업"}
- **상태**: 진행 중
- **메모**: 

## 💡 로컬 환경 특이사항
- **개발 환경**: 
- **특별 설정**: 
- **주의사항**: 

---
**참고**: 이 파일은 Git에 추적되지 않습니다. 개인 작업 환경별 메모용입니다.
EOF

    echo "✅ 로컬 작업 컨텍스트가 생성되었습니다: $local_claude"
}

# 전체 컨텍스트 표시 (Git + 로컬)
show_full_context() {
    echo ""
    echo "🏠🏢 전체 작업 컨텍스트:"
    echo ""
    
    # Git 관리 컨텍스트
    if [[ -f "$PROJECT_CLAUDE" ]]; then
        echo "📋 프로젝트 컨텍스트 (Git 동기화됨):"
        grep -A 8 "현재 작업 컨텍스트\|Current Context" "$PROJECT_CLAUDE" || echo "ℹ️  프로젝트 컨텍스트가 설정되지 않았습니다."
        echo ""
    fi
    
    # 로컬 컨텍스트
    local local_claude="$PROJECT_ROOT/CLAUDE.md.local"
    if [[ -f "$local_claude" ]]; then
        echo "💻 로컬 작업 컨텍스트 (개인 환경):"
        cat "$local_claude"
    else
        echo "ℹ️  로컬 컨텍스트가 없습니다. 'local-context' 명령으로 생성하세요."
    fi
}

# 도움말
show_help() {
    echo "🎯 Claude 지침 관리 도구 v2.1 (집-회사 동기화 지원)"
    echo ""
    echo "📋 명령어:"
    echo "  init                      - 지침 구조 초기화 및 정리"
    echo "  structure                 - 새로운 지침 구조 표시"
    echo "  context                   - 현재 작업 컨텍스트 표시"
    echo "  full-context              - 전체 컨텍스트 (Git + 로컬) 표시"
    echo "  local-context <위치>      - 로컬 작업 컨텍스트 생성"
    echo "  sync                      - 워크트리에 지침 동기화"
    echo "  status                    - 워크트리 지침 상태 확인"
    echo "  optimize                  - Claude Code 최적화 가이드"
    echo "  recommend <작업유형>       - 작업 유형별 가이드 추천"
    echo "  update-context <설명>     - 작업 컨텍스트 업데이트"
    echo "  help                      - 이 도움말 표시"
    echo ""
    echo "🏠🏢 집-회사 동기화:"
    echo "  Git 관리: CLAUDE.md, .claude/ (집-회사 공유)"
    echo "  로컬 관리: CLAUDE.md.local (개인 환경별)"
    echo ""
    echo "📖 작업 유형:"
    echo "  performance, api, frontend, database, llm, search"
    echo ""
    echo "💡 예시:"
    echo "  $0 init                                    # 최초 구조 정리"
    echo "  $0 local-context 집 '성능 최적화 작업'       # 로컬 컨텍스트"
    echo "  $0 full-context                           # 전체 상황 확인"
    echo "  $0 sync                                   # 워크트리 동기화"
    echo "  $0 recommend performance                  # 성능 작업 가이드"
}

# 워크트리 동기화
sync_to_worktrees() {
    echo ""
    echo "🌳 워크트리 동기화를 시작합니다..."
    echo ""
    
    # 현재 워크트리 목록 가져오기
    local worktrees=($(git worktree list --porcelain | grep "worktree " | cut -d' ' -f2))
    local current_worktree="$PROJECT_ROOT"
    local synced_count=0
    
    for worktree in "${worktrees[@]}"; do
        if [[ "$worktree" != "$current_worktree" ]]; then
            echo "📁 워크트리 동기화: $(basename "$worktree")"
            
            # CLAUDE.md 파일 복사
            if [[ -f "$PROJECT_CLAUDE" ]]; then
                cp "$PROJECT_CLAUDE" "$worktree/CLAUDE.md"
                echo "  ✅ CLAUDE.md 동기화 완료"
            fi
            
            # .claude 폴더 전체 복사
            if [[ -d "$PROJECT_CLAUDE_DIR" ]]; then
                rsync -av --delete "$PROJECT_CLAUDE_DIR/" "$worktree/.claude/"
                echo "  ✅ .claude/ 폴더 동기화 완료"
            fi
            
            # 스크립트 파일 복사
            if [[ -f "$PROJECT_ROOT/scripts/claude-guide-manager.sh" ]]; then
                mkdir -p "$worktree/scripts"
                cp "$PROJECT_ROOT/scripts/claude-guide-manager.sh" "$worktree/scripts/"
                echo "  ✅ 관리 스크립트 동기화 완료"
            fi
            
            ((synced_count++))
            echo ""
        fi
    done
    
    if [[ $synced_count -eq 0 ]]; then
        echo "ℹ️  동기화할 워크트리가 없습니다."
    else
        echo "🎉 총 ${synced_count}개의 워크트리에 지침을 동기화했습니다."
    fi
}

# 워크트리 상태 확인
check_worktree_status() {
    echo ""
    echo "🌳 워크트리 지침 상태 확인:"
    echo ""
    
    local worktrees=($(git worktree list --porcelain | grep "worktree " | cut -d' ' -f2))
    local current_worktree="$PROJECT_ROOT"
    
    for worktree in "${worktrees[@]}"; do
        if [[ "$worktree" != "$current_worktree" ]]; then
            echo "📁 $(basename "$worktree"):"
            
            # CLAUDE.md 확인
            if [[ -f "$worktree/CLAUDE.md" ]]; then
                local main_hash=$(md5 -q "$PROJECT_CLAUDE" 2>/dev/null || echo "missing")
                local worktree_hash=$(md5 -q "$worktree/CLAUDE.md" 2>/dev/null || echo "missing")
                
                if [[ "$main_hash" == "$worktree_hash" ]]; then
                    echo "  ✅ CLAUDE.md 동기화됨"
                else
                    echo "  ⚠️  CLAUDE.md 동기화 필요"
                fi
            else
                echo "  ❌ CLAUDE.md 없음"
            fi
            
            # .claude 폴더 확인
            if [[ -d "$worktree/.claude" ]]; then
                echo "  ✅ .claude 폴더 존재"
            else
                echo "  ❌ .claude 폴더 없음"
            fi
            
            echo ""
        fi
    done
}

# 메인 실행 로직
main() {
    case "${1:-help}" in
        init|i)
            init_structure
            create_simplified_project_guide
            ;;
        structure|s)
            show_new_structure
            ;;
        context|ctx)
            if [[ -f "$PROJECT_CLAUDE" ]]; then
                echo ""
                echo "🎯 현재 작업 컨텍스트:"
                echo ""
                grep -A 10 "현재 작업 컨텍스트\|Current Context" "$PROJECT_CLAUDE" || echo "ℹ️  작업 컨텍스트가 설정되지 않았습니다."
            else
                echo "⚠️  프로젝트 CLAUDE.md 파일이 없습니다. 'init' 명령어를 실행하세요."
            fi
            ;;
        full-context|full)
            show_full_context
            ;;
        local-context|local)
            shift
            create_local_context "$@"
            ;;
        sync)
            sync_to_worktrees
            ;;
        status|st)
            check_worktree_status
            ;;
        optimize|opt)
            show_optimization_guide
            ;;
        recommend|rec)
            recommend_guide "$2"
            ;;
        update-context|update)
            shift
            update_context "$@"
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            echo "⚠️  알 수 없는 명령어: $1"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

main "$@"
