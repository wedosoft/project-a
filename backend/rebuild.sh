#!/bin/bash

# 🔄 Docker 컨테이너 재빌드 및 실행 스크립트
# Freshdesk Custom App Backend 재빌드 자동화

set -e  # 에러 발생 시 스크립트 중단

echo "🛑 기존 Docker 컨테이너 중지 및 제거 중..."
docker-compose down

echo "🔨 Docker 이미지 재빌드 및 컨테이너 실행 중..."
docker-compose up --build -d

echo "⏳ 컨테이너 시작 대기 중 (5초)..."
sleep 5

echo "📋 실행 중인 컨테이너 상태 확인:"
docker-compose ps

echo "📝 백엔드 로그 확인 (마지막 20줄):"
docker logs --tail 20 project-a

echo ""
echo "✅ 재빌드 완료!"
echo "🌐 백엔드 서버: http://localhost:8000"
echo "📊 Qdrant 대시보드: http://localhost:6333/dashboard"
echo ""
echo "📜 실시간 로그 확인: docker logs -f project-a"
echo "🔍 API 문서 확인: http://localhost:8000/docs"
