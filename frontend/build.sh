#!/bin/zsh
# filepath: /Users/alan/GitHub/project-a/frontend/build.sh

echo "🚀 CopilotKit POC 빌드 시작"

# Node.js 버전 확인 및 설정
echo "📌 Node.js 버전 설정"
if command -v nvm &> /dev/null; then
  cd "$(dirname "$0")"
  nvm use
else
  echo "⚠️ nvm이 설치되어 있지 않습니다. 수동으로 Node.js 버전을 관리하세요."
  echo "현재 Node.js 버전: $(node -v)"
fi

# 패키지 설치
echo "📦 의존성 패키지 설치"
npm install

# Webpack 빌드
echo "🔨 Webpack 빌드"
npm run build

echo "✅ 빌드 완료"
echo "프로젝트를 FDK로 로컬 실행하려면: fdk run"
