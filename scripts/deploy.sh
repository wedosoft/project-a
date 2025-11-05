#!/bin/bash
# Fly.io 배포 스크립트

set -e

APP_NAME="ai-contact-center-os"

echo "🚀 Fly.io 배포를 시작합니다..."

# Flyctl 설치 확인
if ! command -v flyctl &> /dev/null; then
    echo "❌ flyctl이 설치되어 있지 않습니다."
    echo "다음 명령으로 설치하세요: brew install flyctl"
    exit 1
fi

# 로그인 확인
if ! flyctl auth whoami &> /dev/null; then
    echo "❌ Fly.io에 로그인되어 있지 않습니다."
    echo "다음 명령으로 로그인하세요: flyctl auth login"
    exit 1
fi

echo "✅ Flyctl 설치 및 로그인 확인 완료"

# 앱 존재 확인
if ! flyctl apps list | grep -q "$APP_NAME"; then
    echo "📦 새 앱을 생성합니다: $APP_NAME"
    flyctl apps create "$APP_NAME"
    echo "✅ 앱 생성 완료"
else
    echo "✅ 앱이 이미 존재합니다: $APP_NAME"
fi

# Secrets 설정 여부 확인
echo ""
echo "🔐 환경 변수(Secrets) 확인..."
if ! flyctl secrets list &> /dev/null || [ $(flyctl secrets list | wc -l) -lt 3 ]; then
    echo "⚠️  Secrets가 설정되어 있지 않거나 부족합니다."
    echo "Secrets를 설정하시겠습니까? (y/n)"
    read -r response
    if [[ "$response" == "y" ]]; then
        if [ -f "scripts/deploy_secrets.sh" ]; then
            ./scripts/deploy_secrets.sh
        else
            echo "❌ scripts/deploy_secrets.sh를 찾을 수 없습니다."
            echo "수동으로 Secrets를 설정하세요. 가이드: docs/FLY_IO_DEPLOYMENT.md"
            exit 1
        fi
    else
        echo "⚠️  Secrets 없이 배포를 진행합니다. 앱이 정상 작동하지 않을 수 있습니다."
    fi
else
    echo "✅ Secrets 설정 확인 완료"
    echo "현재 설정된 Secrets:"
    flyctl secrets list
fi

# 배포
echo ""
echo "📦 Docker 이미지 빌드 및 배포 중..."
flyctl deploy --ha=false

# 배포 상태 확인
echo ""
echo "🔍 배포 상태 확인 중..."
flyctl status

# 헬스 체크
echo ""
echo "🏥 헬스 체크 확인 중..."
sleep 5
flyctl checks list

# 최종 안내
echo ""
echo "✅ 배포가 완료되었습니다!"
echo ""
echo "📊 앱 정보:"
flyctl info
echo ""
echo "🌐 앱 URL: https://$APP_NAME.fly.dev"
echo "🏥 헬스 체크: https://$APP_NAME.fly.dev/health"
echo ""
echo "📝 유용한 명령어:"
echo "  - 로그 확인: flyctl logs"
echo "  - 앱 재시작: flyctl apps restart $APP_NAME"
echo "  - 앱 상태: flyctl status"
echo "  - Secrets 확인: flyctl secrets list"
echo ""
echo "📚 자세한 가이드: docs/FLY_IO_DEPLOYMENT.md"
