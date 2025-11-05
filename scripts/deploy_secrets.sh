#!/bin/bash
# Fly.io Secrets 설정 스크립트
# .env 파일의 환경 변수를 Fly.io Secrets로 설정

set -e

echo "🚀 Fly.io Secrets 설정을 시작합니다..."

# .env 파일 존재 확인
if [ ! -f .env ]; then
    echo "❌ .env 파일을 찾을 수 없습니다."
    exit 1
fi

echo "📝 .env 파일에서 환경 변수를 읽어옵니다..."

# .env 파일 읽기 및 Secrets 설정
while IFS='=' read -r key value || [ -n "$key" ]; do
    # 주석과 빈 줄 무시
    if [[ $key =~ ^#.* ]] || [[ -z "$key" ]]; then
        continue
    fi
    
    # 앞뒤 공백 제거
    key=$(echo "$key" | xargs)
    value=$(echo "$value" | xargs)
    
    # 빈 값 건너뛰기
    if [ -z "$value" ]; then
        echo "⚠️  $key: 값이 비어있어 건너뜁니다."
        continue
    fi
    
    # FASTAPI_ENV, FASTAPI_HOST, FASTAPI_PORT, LOG_LEVEL은 fly.toml에 설정되어 있으므로 제외
    if [[ "$key" == "FASTAPI_ENV" ]] || [[ "$key" == "FASTAPI_HOST" ]] || \
       [[ "$key" == "FASTAPI_PORT" ]] || [[ "$key" == "LOG_LEVEL" ]]; then
        echo "⏭️  $key: fly.toml에 이미 설정되어 있어 건너뜁니다."
        continue
    fi
    
    echo "✅ $key 설정 중..."
    flyctl secrets set "$key=$value" --stage
    
done < .env

echo ""
echo "🎉 모든 Secrets가 staging 되었습니다."
echo "💡 실제로 적용하려면 다음 명령을 실행하세요:"
echo "   flyctl secrets deploy"
echo ""
echo "또는 즉시 배포하려면:"
echo "   flyctl deploy"
