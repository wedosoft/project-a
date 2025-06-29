#!/bin/bash

# 하이브리드 검색 프로젝트 상태 체크 스크립트
# 새 세션에서 빠른 상태 파악을 위한 도구

echo "🔍 하이브리드 검색 개선 프로젝트 현재 상태"
echo "================================================"

# Git 브랜치 확인
echo "📦 Git 브랜치 상태:"
git branch --show-current
git status --porcelain

echo ""

# 핵심 파일 존재 확인
echo "📁 핵심 파일 상태:"
FILES=(
    "docs/HYBRID_SEARCH_STATUS.md"
    "docs/HYBRID_SEARCH_ENHANCEMENT_PLAN.md" 
    "backend/api/routes/init.py"
    "backend/core/search/hybrid.py"
)

for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        echo "✅ $file"
    else
        echo "❌ $file (누락)"
    fi
done

echo ""

# 마지막 커밋 정보
echo "📝 마지막 커밋:"
git log --oneline -1

echo ""

# 상태 파일에서 현재 단계 추출
echo "🎯 현재 진행 단계:"
if [ -f "docs/HYBRID_SEARCH_STATUS.md" ]; then
    grep -A 1 "3단계 프로세스 상태" docs/HYBRID_SEARCH_STATUS.md | tail -1
    echo ""
    echo "📊 전체 진행률:"
    grep "전체 진행률" docs/HYBRID_SEARCH_STATUS.md
else
    echo "❌ 상태 파일이 없습니다."
fi

echo ""
echo "💡 다음 단계: docs/HYBRID_SEARCH_STATUS.md 파일을 먼저 읽어주세요!"
echo "================================================"
