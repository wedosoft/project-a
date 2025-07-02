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

# 워크트리 생성
echo -e "${GREEN}⚙️  워크트리 생성 중...${NC}"
git worktree add "../project-a-${worktree_name}" "$branch_name"

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ 워크트리 생성 실패${NC}"
    exit 1
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

# 자동으로 디렉토리 이동 여부 묻기
read -p "지금 바로 워크트리로 이동하시겠습니까? (y/n): " auto_cd

if [ "$auto_cd" = "y" ] || [ "$auto_cd" = "Y" ]; then
    cd "$worktree_path"
    echo -e "${GREEN}📁 $(pwd) 로 이동했습니다${NC}"
    echo -e "${YELLOW}이제 'claude-code' 명령어를 실행하세요!${NC}"
fi