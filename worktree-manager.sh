#!/bin/bash
# worktree-manager.sh - 워크트리 관리 유틸리티

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}🔧 워크트리 관리자${NC}"
echo "====================="

# 메뉴 선택
echo -e "${YELLOW}원하는 작업을 선택하세요:${NC}"
echo "1. 📋 워크트리 목록 보기"
echo "2. 🗑️  워크트리 제거"
echo "3. 🧹 완료된 워크트리 일괄 정리"
echo "4. 📊 워크트리 상태 확인"
echo "5. ❌ 종료"

read -p "선택 (1-5): " choice

case $choice in
    1)
        echo -e "${GREEN}📋 현재 워크트리 목록:${NC}"
        git worktree list
        ;;
    2)
        echo -e "${GREEN}🗑️  제거할 워크트리 선택:${NC}"
        git worktree list
        echo ""
        read -p "제거할 워크트리 경로를 입력하세요: " worktree_path
        if [ -d "$worktree_path" ]; then
            git worktree remove "$worktree_path"
            echo -e "${GREEN}✅ 워크트리 제거 완료${NC}"
        else
            echo -e "${RED}❌ 워크트리를 찾을 수 없습니다${NC}"
        fi
        ;;
    3)
        echo -e "${GREEN}🧹 완료된 워크트리 정리 중...${NC}"
        # 병합된 브랜치 찾기
        merged_branches=$(git branch --merged | grep -v "^\*\|dev\|main\|master")
        if [ -n "$merged_branches" ]; then
            echo -e "${YELLOW}병합된 브랜치들:${NC}"
            echo "$merged_branches"
            read -p "이 브랜치들의 워크트리를 정리하시겠습니까? (y/n): " confirm
            if [ "$confirm" = "y" ] || [ "$confirm" = "Y" ]; then
                for branch in $merged_branches; do
                    worktree_path=$(git worktree list --porcelain | grep -B1 "branch refs/heads/$branch" | head -1 | cut -d' ' -f2)
                    if [ -n "$worktree_path" ] && [ "$worktree_path" != "$(pwd)" ]; then
                        echo -e "${GREEN}제거 중: $worktree_path${NC}"
                        git worktree remove "$worktree_path" 2>/dev/null || true
                    fi
                done
            fi
        else
            echo -e "${GREEN}정리할 워크트리가 없습니다${NC}"
        fi
        ;;
    4)
        echo -e "${GREEN}📊 워크트리 상태:${NC}"
        git worktree list --porcelain
        echo ""
        echo -e "${GREEN}📈 통계:${NC}"
        total_worktrees=$(git worktree list | wc -l)
        echo -e "${BLUE}총 워크트리 수: $total_worktrees${NC}"
        ;;
    5)
        echo -e "${GREEN}👋 종료합니다${NC}"
        exit 0
        ;;
    *)
        echo -e "${RED}❌ 잘못된 선택입니다${NC}"
        ;;
esac
