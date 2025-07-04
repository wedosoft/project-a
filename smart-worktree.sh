#!/bin/bash
# smart-worktree.sh - 템플릿 기반 워크트리 생성 시스템

# 색상 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}🚀 스마트 워크트리 생성기${NC}"
echo "================================"

# 작업 유형 선택
echo -e "${YELLOW}작업 유형을 선택하세요:${NC}"
echo "1. 🐛 버그 수정 (Bug Fix)"
echo "2. ⚡ 성능 최적화 (Performance)"  
echo "3. 🧪 실험/테스트 (Experiment)"
echo "4. ✨ 새 기능 추가 (Feature)"
echo "5. 🔧 리팩토링 (Refactor)"
echo "6. 📚 문서화 (Documentation)"
echo "7. 🎨 UI/UX 개선 (Frontend)"
echo "8. 🔒 보안 개선 (Security)"

read -p "선택 (1-8): " work_type

# 작업 설명 입력
read -p "간단한 작업 설명: " description

# 예상 작업 시간
echo -e "${YELLOW}예상 작업 시간:${NC}"
echo "1. 빠른 작업 (30분 이내)"
echo "2. 중간 작업 (2시간 이내)"  
echo "3. 긴 작업 (하루 이상)"
read -p "선택 (1-3): " duration

# 워크트리 이름 생성
case $work_type in
    1) prefix="bugfix" ;;
    2) prefix="perf" ;;
    3) prefix="exp" ;;
    4) prefix="feat" ;;
    5) prefix="refactor" ;;
    6) prefix="docs" ;;
    7) prefix="ui" ;;
    8) prefix="sec" ;;
esac

timestamp=$(date +%m%d_%H%M)
worktree_name="${prefix}-${timestamp}"
branch_name="feature/${worktree_name}"

echo -e "${BLUE}📁 워크트리 이름: ${worktree_name}${NC}"
echo -e "${BLUE}🌿 브랜치 이름: ${branch_name}${NC}"

# 브랜치와 워크트리를 동시에 생성
echo -e "${GREEN}⚙️  브랜치와 워크트리 생성 중...${NC}"
if git worktree add -b "$branch_name" "../project-a-${worktree_name}"; then
    echo -e "${GREEN}✅ 워크트리와 브랜치 생성 완료${NC}"
else
    echo -e "${RED}❌ 워크트리 생성 실패${NC}"
    echo -e "${YELLOW}💡 브랜치가 이미 존재하는 경우 기존 브랜치를 사용합니다...${NC}"
    
    # 브랜치가 이미 존재하는 경우 기존 브랜치로 워크트리 생성
    if git worktree add "../project-a-${worktree_name}" "$branch_name"; then
        echo -e "${GREEN}✅ 기존 브랜치로 워크트리 생성 완료${NC}"
    else
        echo -e "${RED}❌ 워크트리 생성 최종 실패${NC}"
        exit 1
    fi
fi

worktree_path="../project-a-${worktree_name}"

# 작업 유형별 템플릿 생성
create_claude_md() {
    local work_type=$1
    local description="$2"
    local duration=$3
    
    case $work_type in
        1) # 버그 수정
            cat > "$worktree_path/CLAUDE.md" << EOF
# 🐛 버그 수정: ${description}

## 작업 유형: Bug Fix
## 우선순위: 높음
## 예상 시간: $(get_duration_text $duration)

## 📋 작업 지침
1. **빠른 진단**: 에러 로그, 스택 트레이스부터 확인
2. **최소 수정**: 버그 원인만 정확히 수정
3. **사이드 이펙트 방지**: 다른 기능에 영향 주지 않도록

## 🎯 작업 범위
- 에러 관련 파일만 수정
- 로그, 예외 처리 개선
- 테스트 케이스 추가

## ⛔ 금지사항
- 새로운 기능 추가
- 대규모 리팩토링
- 설정 파일 수정 (꼭 필요한 경우만)
- UI/UX 변경

## 🚀 빠른 시작 프롬프트
"프로젝트에서 다음 버그를 찾아서 수정해주세요: '${description}'
먼저 관련 파일 3개만 찾아서 나열하고, 승인받으면 수정 시작하겠습니다."

## 🎯 Claude Code 7-Rule 워크플로우
1. **계획**: 버그 원인을 먼저 분석하고 수정 계획 수립
2. **체크리스트**: 아래 완료 체크리스트를 순서대로 확인
3. **검토**: 각 단계마다 결과를 검토하고 다음 단계 진행
4. **보안**: 수정이 새로운 취약점을 만들지 않는지 확인
5. **학습**: 버그의 근본 원인과 예방법을 문서화
6. **피드백**: 수정 후 동작을 검증하고 개선점 기록
7. **반복**: 유사한 버그를 예방하기 위한 패턴 정리

## ✅ 완료 체크리스트
- [ ] 버그 재현 확인
- [ ] 원인 파악 완료  
- [ ] 수정 코드 구현
- [ ] 테스트 통과 확인
- [ ] 사이드 이펙트 없음 확인
EOF
            ;;
            
        2) # 성능 최적화
            cat > "$worktree_path/CLAUDE.md" << EOF
# ⚡ 성능 최적화: ${description}

## 작업 유형: Performance Optimization
## 우선순위: 중간
## 예상 시간: $(get_duration_text $duration)

## 📋 작업 지침
1. **병목 지점 분석**: 프로파일링으로 느린 부분 찾기
2. **측정 가능한 개선**: 개선 전후 성능 수치 비교
3. **점진적 최적화**: 작은 개선들을 누적

## 🎯 작업 범위
- backend/core/database/ (DB 쿼리 최적화)
- backend/core/search/ (검색 성능 개선)
- backend/core/processing/ (데이터 처리 속도)
- 메모리 사용량 최적화

## ⛔ 금지사항
- 기능 변경 또는 제거
- 새로운 의존성 추가 (꼭 필요한 경우만)
- API 인터페이스 변경

## 🚀 빠른 시작 프롬프트
"다음 성능 최적화를 해주세요: '${description}'
1. 현재 성능 병목 지점 3곳 찾기
2. 개선 방안 제시 (목표: 30% 향상)
3. 승인받으면 구현 시작"

## 🎯 Claude Code 7-Rule 워크플로우
1. **계획**: 성능 병목 지점을 체계적으로 분석하고 우선순위 결정
2. **체크리스트**: 측정-최적화-검증 사이클을 반복
3. **검토**: 각 최적화마다 성능 개선 수치를 측정하고 검토
4. **보안**: 최적화가 보안성이나 데이터 무결성에 영향 없는지 확인
5. **학습**: 성능 최적화 기법과 측정 방법을 문서화
6. **피드백**: 최적화 후 전체 시스템 성능을 모니터링
7. **반복**: 성능 개선 노하우를 다른 영역에 적용

## ✅ 완료 체크리스트
- [ ] 현재 성능 측정 완료
- [ ] 병목 지점 파악
- [ ] 최적화 코드 구현
- [ ] 성능 개선 확인 (수치로)
- [ ] 기존 기능 정상 동작 확인
EOF
            ;;
            
        3) # 실험/테스트
            cat > "$worktree_path/CLAUDE.md" << EOF
# 🧪 실험/테스트: ${description}

## 작업 유형: Experiment
## 우선순위: 낮음
## 예상 시간: $(get_duration_text $duration)

## 📋 작업 지침
1. **안전한 실험**: 기존 시스템에 영향 주지 않기
2. **별도 파일**: 새 파일로 실험, 기존 파일 최소 수정
3. **문서화**: 실험 과정과 결과 기록

## 🎯 작업 범위
- 새로운 접근법 테스트
- 라이브러리/도구 평가
- 프로토타입 개발
- A/B 테스트 구현

## ⛔ 금지사항
- 프로덕션 코드 직접 수정
- 기존 API 변경
- 데이터베이스 스키마 변경

## 🚀 빠른 시작 프롬프트
"다음 실험을 안전하게 진행해주세요: '${description}'
1. experiments/ 폴더에 별도 파일 생성
2. 기존 시스템에 영향 없이 테스트
3. 결과를 README_EXPERIMENT.md에 기록"

## ✅ 완료 체크리스트
- [ ] 실험 계획 수립
- [ ] 별도 환경에서 테스트
- [ ] 결과 측정 및 분석
- [ ] 문서화 완료
- [ ] 기존 시스템 영향 없음 확인
EOF
            ;;
            
        4) # 새 기능 추가
            cat > "$worktree_path/CLAUDE.md" << EOF
# ✨ 새 기능: ${description}

## 작업 유형: Feature Development
## 우선순위: 중간
## 예상 시간: $(get_duration_text $duration)

## 📋 작업 지침
1. **설계 우선**: API 설계부터 시작
2. **점진적 개발**: 작은 단위로 구현
3. **테스트 포함**: 기능과 함께 테스트 작성

## 🎯 작업 범위
- 새로운 모듈/기능 구현
- API 엔드포인트 추가
- 관련 테스트 작성
- 문서 업데이트

## ⛔ 금지사항
- 기존 기능 수정 (꼭 필요한 경우만)
- 데이터베이스 구조 대대적 변경
- 외부 의존성 무분별 추가

## 🚀 빠른 시작 프롬프트
"다음 새 기능을 개발해주세요: '${description}'
1. API 설계 먼저 제시
2. 구현 계획 설명
3. 승인받으면 단계별 개발 시작"

## 🎯 Claude Code 7-Rule 워크플로우
1. **계획**: 기능 명세와 API 설계를 상세히 수립
2. **체크리스트**: 설계-구현-테스트-문서화 단계를 순차 진행
3. **검토**: 각 구현 단계마다 설계 의도와 일치하는지 검토
4. **보안**: 새 기능이 보안 취약점을 만들지 않는지 검증
5. **학습**: 개발 과정에서 배운 패턴과 기법을 문서화
6. **피드백**: 기능 완성 후 사용성과 성능을 평가
7. **반복**: 개발한 패턴을 다른 기능에도 적용

## ✅ 완료 체크리스트
- [ ] 기능 명세 확정
- [ ] API 설계 완료
- [ ] 핵심 로직 구현
- [ ] 테스트 케이스 작성
- [ ] 문서 업데이트
EOF
            ;;
            
        5) # 리팩토링
            cat > "$worktree_path/CLAUDE.md" << EOF
# 🔧 리팩토링: ${description}

## 작업 유형: Code Refactoring
## 우선순위: 중간
## 예상 시간: $(get_duration_text $duration)

## 📋 작업 지침
1. **기능 보존**: 외부 동작은 동일하게 유지
2. **점진적 개선**: 작은 단위로 리팩토링
3. **테스트 필수**: 각 단계마다 테스트 확인

## 🎯 작업 범위
- 코드 구조 개선
- 중복 코드 제거
- 네이밍 개선
- 모듈 분리/통합

## ⛔ 금지사항
- 기능 변경 또는 추가
- API 인터페이스 변경
- 대규모 아키텍처 변경

## 🚀 빠른 시작 프롬프트
"다음 리팩토링을 진행해주세요: '${description}'
1. 현재 코드 구조 분석
2. 개선 방안 제시
3. 단계별 리팩토링 계획 승인받고 시작"

## 🎯 Claude Code 7-Rule 워크플로우
1. **계획**: 리팩토링 범위와 목표를 명확히 정의
2. **체크리스트**: 각 단계마다 테스트를 통해 기능 보존 확인
3. **검토**: 리팩토링된 코드의 가독성과 유지보수성 평가
4. **보안**: 코드 변경이 보안성에 영향 없는지 검증
5. **학습**: 리팩토링 패턴과 기법을 문서화
6. **피드백**: 리팩토링 후 코드 품질 지표 측정
7. **반복**: 배운 리팩토링 기법을 다른 모듈에 적용

## ✅ 완료 체크리스트
- [ ] 리팩토링 계획 수립
- [ ] 기존 테스트 모두 통과
- [ ] 코드 품질 개선 확인
- [ ] 성능 저하 없음 확인
- [ ] 문서 업데이트
EOF
            ;;
            
        6) # 문서화
            cat > "$worktree_path/CLAUDE.md" << EOF
# 📚 문서화: ${description}

## 작업 유형: Documentation
## 우선순위: 낮음
## 예상 시간: $(get_duration_text $duration)

## 📋 작업 지침
1. **명확하고 간결**: 이해하기 쉽게 작성
2. **실용적 예시**: 코드 예제 포함
3. **최신 상태 유지**: 코드와 문서 동기화

## 🎯 작업 범위
- API 문서 작성/업데이트
- README, 설치 가이드
- 코드 주석 개선
- 아키텍처 문서

## ⛔ 금지사항
- 코드 변경 (문서화 목적 외)
- 불필요한 상세 설명

## 🚀 빠른 시작 프롬프트
"다음 문서화 작업을 해주세요: '${description}'
1. 현재 문서 상태 확인
2. 부족한 부분 파악
3. 명확하고 실용적인 문서 작성"

## 🎯 Claude Code 7-Rule 워크플로우
1. **계획**: 문서화할 내용과 대상 독자를 명확히 정의
2. **체크리스트**: 구조-내용-예제-검토 단계를 순차 진행
3. **검토**: 문서의 명확성과 완성도를 다각도로 평가
4. **보안**: 문서에 민감한 정보가 노출되지 않는지 확인
5. **학습**: 효과적인 문서화 기법과 구조를 정리
6. **피드백**: 문서 사용자의 피드백을 수집하고 개선
7. **반복**: 문서화 패턴을 다른 프로젝트에도 적용

## ✅ 완료 체크리스트
- [ ] 문서 구조 계획
- [ ] 내용 작성 완료
- [ ] 코드 예제 포함
- [ ] 오타/문법 검토
- [ ] 링크 정상 동작 확인
EOF
            ;;
            
        7) # UI/UX 개선
            cat > "$worktree_path/CLAUDE.md" << EOF
# 🎨 UI/UX 개선: ${description}

## 작업 유형: Frontend/UI
## 우선순위: 중간
## 예상 시간: $(get_duration_text $duration)

## 📋 작업 지침
1. **사용자 중심**: 사용성 개선에 집중
2. **일관성 유지**: 기존 디자인 시스템 준수
3. **반응형 고려**: 다양한 화면 크기 지원

## 🎯 작업 범위
- frontend/ 폴더 내 파일들
- 사용자 인터페이스 개선
- 사용성(UX) 향상
- 접근성 개선

## ⛔ 금지사항
- 백엔드 로직 변경
- API 변경 (꼭 필요한 경우만)
- 대규모 디자인 시스템 변경

## 🚀 빠른 시작 프롬프트
"다음 UI/UX 개선을 해주세요: '${description}'
1. 현재 UI 분석
2. 개선 방안 제시
3. 사용자 경험 향상 방법 승인받고 구현"

## ✅ 완료 체크리스트
- [ ] 현재 UI 문제점 파악
- [ ] 개선안 설계
- [ ] 구현 완료
- [ ] 다양한 화면 크기 테스트
- [ ] 접근성 확인
EOF
            ;;
            
        8) # 보안 개선
            cat > "$worktree_path/CLAUDE.md" << EOF
# 🔒 보안 개선: ${description}

## 작업 유형: Security Enhancement
## 우선순위: 높음
## 예상 시간: $(get_duration_text $duration)

## 📋 작업 지침
1. **보안 우선**: 기능보다 보안이 우선
2. **최소 권한**: 필요한 권한만 부여
3. **검증 철저**: 입력값 검증 강화

## 🎯 작업 범위
- 인증/인가 시스템
- 입력값 검증 및 sanitization
- API 보안 강화
- 민감 정보 보호

## ⛔ 금지사항
- 보안을 위해 기능 제거 (신중히 검토)
- 과도한 보안으로 사용성 크게 해치기

## 🚀 빠른 시작 프롬프트
"다음 보안 개선을 해주세요: '${description}'
1. 현재 보안 취약점 분석
2. 보안 강화 방안 제시
3. 단계별 보안 개선 실행"

## ✅ 완료 체크리스트
- [ ] 보안 취약점 파악
- [ ] 보안 강화 방안 구현
- [ ] 인증/인가 테스트
- [ ] 보안 스캔 통과
- [ ] 문서 업데이트
EOF
            ;;
    esac
}

# 시간 텍스트 변환 함수
get_duration_text() {
    case $1 in
        1) echo "30분 이내 (빠른 작업)" ;;
        2) echo "2시간 이내 (중간 작업)" ;;
        3) echo "하루 이상 (긴 작업)" ;;
    esac
}

# CLAUDE.md 생성
echo -e "${GREEN}📝 CLAUDE.md 생성 중...${NC}"
create_claude_md $work_type "$description" $duration

# 공통 파일 동기화 (선택사항)
if [ -f "project-a/.gitignore" ]; then
    echo -e "${GREEN}🔗 공통 파일 동기화 중...${NC}"
    ln -sf "../../project-a/.gitignore" "$worktree_path/.gitignore"
    ln -sf "../../project-a/.env" "$worktree_path/.env" 2>/dev/null
    ln -sf "../../project-a/requirements.txt" "$worktree_path/requirements.txt" 2>/dev/null
fi

# 완료 메시지
echo ""
echo -e "${GREEN}🎉 워크트리 생성 완료!${NC}"
echo -e "${CYAN}📍 위치: ${worktree_path}${NC}"
echo -e "${CYAN}🌿 브랜치: ${branch_name}${NC}"
echo ""
echo -e "${YELLOW}🚀 바로 시작하기:${NC}"
echo -e "${BLUE}cd ${worktree_path} && claude-code${NC}"
echo ""
echo -e "${YELLOW}💡 완료 후 정리:${NC}"
echo -e "${BLUE}git worktree remove ${worktree_path}${NC}"
echo ""

# 작업 방식 선택
echo -e "${YELLOW}어떻게 작업을 시작하시겠습니까?${NC}"
echo "1. 🗂️  VS Code 작업영역에 추가 (추천)"
echo "2. 📁 새 VS Code 창에서 워크트리 열기"
echo "3. 💻 터미널에서 바로 작업"
echo "4. ⏭️  나중에 직접 선택"

read -p "선택 (1-4): " work_mode

case $work_mode in
    1)
        echo -e "${GREEN}🗂️  VS Code 작업영역에 워크트리를 추가합니다...${NC}"
        if command -v code &> /dev/null; then
            code --add "$worktree_path"
            echo -e "${GREEN}✅ 작업영역에 추가 완료${NC}"
            echo -e "${CYAN}💡 VS Code 탐색기에서 새 워크트리 폴더를 확인하세요${NC}"
        else
            echo -e "${YELLOW}⚠️  VS Code가 설치되지 않았습니다${NC}"
        fi
        ;;
    2)
        echo -e "${GREEN}📁 새 VS Code 창에서 워크트리를 엽니다...${NC}"
        if command -v code &> /dev/null; then
            code "$worktree_path"
            echo -e "${GREEN}✅ 새 창에서 열기 완료${NC}"
        else
            echo -e "${YELLOW}⚠️  VS Code가 설치되지 않았습니다${NC}"
        fi
        ;;
    3)
        echo -e "${GREEN}💻 터미널 세션을 시작합니다...${NC}"
        echo -e "${CYAN}다음 명령어를 실행하세요:${NC}"
        echo -e "${BLUE}cd ${worktree_path}${NC}"
        ;;
    4)
        echo -e "${GREEN}⏭️  나중에 선택하세요${NC}"
        ;;
esac

# 워크트리 정리 기능 추가
echo ""
echo -e "${YELLOW}📋 유용한 명령어들:${NC}"
echo -e "${BLUE}• 현재 워크트리 목록: git worktree list${NC}"
echo -e "${BLUE}• 워크트리 제거: git worktree remove ${worktree_path}${NC}"
echo -e "${BLUE}• 모든 워크트리 상태: git worktree list --porcelain${NC}"

# 기존 워크트리 정리 제안
existing_worktrees=$(git worktree list --porcelain | grep -c "^worktree")
if [ "$existing_worktrees" -gt 2 ]; then
    echo ""
    echo -e "${YELLOW}⚠️  워크트리가 ${existing_worktrees}개 있습니다. 정리가 필요할 수 있습니다.${NC}"
    echo -e "${CYAN}git worktree list 명령어로 확인해보세요.${NC}"
fi