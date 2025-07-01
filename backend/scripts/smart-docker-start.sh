#!/bin/bash
"""
스마트 Docker 시작 스크립트
환경을 자동 감지하여 적절한 Docker Compose 설정 선택
"""

set -e

echo "🔍 환경 감지 중..."

# 환경 변수
COMPOSE_FILES="docker-compose.yml"
GPU_SUPPORT=""
ENVIRONMENT=""

# 1. 플랫폼 감지
if [[ "$OSTYPE" == "darwin"* ]]; then
    ENVIRONMENT="local"
    echo "📱 플랫폼: macOS (로컬 개발)"
    
elif curl -s --max-time 3 http://169.254.169.254/latest/meta-data/ > /dev/null 2>&1; then
    ENVIRONMENT="aws"
    INSTANCE_TYPE=$(curl -s http://169.254.169.254/latest/meta-data/instance-type)
    echo "☁️ 플랫폼: AWS EC2 ($INSTANCE_TYPE)"
    
else
    ENVIRONMENT="production"
    echo "🏭 플랫폼: 프로덕션 (기타)"
fi

# 2. GPU 감지
if command -v nvidia-smi &> /dev/null; then
    GPU_INFO=$(nvidia-smi --query-gpu=name --format=csv,noheader,nounits 2>/dev/null | head -1)
    if [ ! -z "$GPU_INFO" ]; then
        echo "🚀 GPU 감지됨: $GPU_INFO"
        GPU_SUPPORT="gpu"
        
        # Docker nvidia runtime 확인
        if docker info 2>/dev/null | grep -q nvidia; then
            echo "✅ NVIDIA Docker runtime 사용 가능"
            COMPOSE_FILES="$COMPOSE_FILES -f docker-compose.gpu.yml"
        else
            echo "⚠️ NVIDIA Docker runtime 없음 - CPU fallback"
        fi
    fi
elif [[ "$OSTYPE" == "darwin"* ]] && sysctl machdep.cpu.brand_string | grep -q "Apple"; then
    echo "🍎 Apple Silicon 감지됨 (MPS 지원)"
    GPU_SUPPORT="mps"
else
    echo "💻 GPU 없음 - CPU 모드"
    GPU_SUPPORT="cpu"
fi

# 3. 환경별 설정 파일 추가
case $ENVIRONMENT in
    "local")
        COMPOSE_FILES="$COMPOSE_FILES -f docker-compose.local.yml"
        ;;
    "aws")
        COMPOSE_FILES="$COMPOSE_FILES -f docker-compose.aws.yml"
        ;;
    "production")
        # 프로덕션 기본 설정 사용
        ;;
esac

# 4. 환경 요약
echo ""
echo "📋 환경 요약:"
echo "  플랫폼: $ENVIRONMENT"
echo "  GPU 지원: $GPU_SUPPORT"
echo "  Compose 파일: $COMPOSE_FILES"
echo ""

# 5. Docker Compose 실행
echo "🚀 Docker Compose 시작..."
echo "실행 명령어: docker-compose $COMPOSE_FILES up"
echo ""

# 사용자 확인
read -p "계속하시겠습니까? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    exec docker-compose $COMPOSE_FILES up "$@"
else
    echo "중단됨"
    exit 0
fi