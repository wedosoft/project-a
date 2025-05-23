#!/bin/zsh

# 🔍 환경변수 및 개발환경 점검 스크립트 (macOS + zsh)
echo "🔍 Freshdesk Custom App Backend - 환경변수 점검"
echo "=================================================="

# backend 폴더 내에서 실행 전제
echo "\n=== [1] Python 버전 확인 ==="
python --version
python_version=$(python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
if [ "$python_version" = "3.10" ]; then
  echo "✅ Python 3.10 버전 확인됨"
else
  echo "⚠️  Python 3.10이 권장됩니다 (현재: $python_version)"
fi

echo "\n=== [2] 가상환경 및 패키지 확인 ==="
if [ -d ".venv" ]; then
  source .venv/bin/activate
  echo "✅ 가상환경 활성화됨"
  
  if [ -f "requirements.txt" ]; then
    echo "📦 필수 패키지 설치 상태 확인 중..."
    pip list | grep -E "(fastapi|uvicorn|pydantic|httpx|qdrant-client)" || echo "⚠️  일부 필수 패키지가 누락되었을 수 있습니다"
  else
    echo "❌ requirements.txt 파일이 없습니다"
  fi
else
  echo "⚠️  .venv 폴더가 없습니다. 가상환경을 생성하세요:"
  echo "   python -m venv .venv && source .venv/bin/activate"
fi

echo "\n=== [3] 환경변수 파일 및 주요 키 확인 ==="
if [ -f .env ]; then
  echo "✅ .env 파일 존재"
  
  # 필수 환경변수 체크
  required_vars=("FRESHDESK_DOMAIN" "FRESHDESK_API_KEY" "QDRANT_URL" "QDRANT_API_KEY" "OPENAI_API_KEY")
  
  for var in "${required_vars[@]}"; do
    if grep -q "^${var}=" .env && ! grep -q "^${var}=your-" .env; then
      echo "✅ $var 설정됨"
    else
      echo "❌ $var 누락 또는 기본값 상태"
    fi
  done
  
  # 선택적 환경변수 체크
  optional_vars=("ANTHROPIC_API_KEY" "GOOGLE_API_KEY" "COMPANY_ID")
  echo "\n--- 선택적 환경변수 ---"
  for var in "${optional_vars[@]}"; do
    if grep -q "^${var}=" .env && ! grep -q "^${var}=your-" .env; then
      echo "✅ $var 설정됨"
    else
      echo "○ $var 선택사항 (미설정)"
    fi
  done
  
else
  echo "❌ .env 파일이 없습니다!"
  echo "📋 다음 명령으로 생성하세요:"
  echo "   cp ../.env.example .env"
  echo "   그 후 .env 파일을 편집하여 실제 API 키를 입력하세요"
fi

echo "\n=== [4] 프로젝트 구조 확인 ==="
required_dirs=("api" "core" "freshdesk" "data")
for dir in "${required_dirs[@]}"; do
  if [ -d "$dir" ]; then
    echo "✅ $dir/ 디렉토리 존재"
  else
    echo "❌ $dir/ 디렉토리 누락"
  fi
done

required_files=("api/main.py" "core/llm_router.py" "core/vectordb.py" "freshdesk/fetcher.py")
for file in "${required_files[@]}"; do
  if [ -f "$file" ]; then
    echo "✅ $file 파일 존재"
  else
    echo "❌ $file 파일 누락"
  fi
done

echo "\n=== [5] 캐시 및 데이터 디렉토리 확인 ==="
if [ -d "attachment_cache" ]; then
  cache_count=$(ls -1 attachment_cache 2>/dev/null | wc -l | xargs)
  echo "✅ attachment_cache/ 디렉토리 존재 (파일 수: $cache_count)"
else
  echo "○ attachment_cache/ 디렉토리 없음 (자동 생성됨)"
fi

if [ -d "data" ]; then
  echo "✅ data/ 디렉토리 존재"
else
  echo "○ data/ 디렉토리 없음 (자동 생성됨)"
fi

echo "\n=== [6] API 연결 테스트 (선택적) ==="
if [ -f .env ]; then
  source .env
  
  # OpenAI API 테스트
  if [ ! -z "$OPENAI_API_KEY" ] && [ "$OPENAI_API_KEY" != "your-openai-api-key" ]; then
    echo "🔍 OpenAI API 연결 테스트 중..."
    response=$(curl -s -w "%{http_code}" -o /dev/null \
      https://api.openai.com/v1/models \
      -H "Authorization: Bearer $OPENAI_API_KEY" \
      -H "Content-Type: application/json")
    
    if [ "$response" = "200" ]; then
      echo "✅ OpenAI API 연결 성공"
    else
      echo "❌ OpenAI API 연결 실패 (HTTP: $response)"
    fi
  else
    echo "○ OpenAI API 키 미설정"
  fi
  
  # Freshdesk API 테스트
  if [ ! -z "$FRESHDESK_API_KEY" ] && [ ! -z "$FRESHDESK_DOMAIN" ] && \
     [ "$FRESHDESK_API_KEY" != "your-freshdesk-api-key" ]; then
    echo "🔍 Freshdesk API 연결 테스트 중..."
    response=$(curl -s -w "%{http_code}" -o /dev/null \
      -u "$FRESHDESK_API_KEY:X" \
      "https://$FRESHDESK_DOMAIN/api/v2/tickets?per_page=1")
    
    if [ "$response" = "200" ]; then
      echo "✅ Freshdesk API 연결 성공"
    else
      echo "❌ Freshdesk API 연결 실패 (HTTP: $response)"
    fi
  else
    echo "○ Freshdesk API 설정 미완료"
  fi
else
  echo "○ .env 파일 없음으로 API 테스트 건너뜀"
fi

echo "\n=================================================="
echo "🎯 환경 점검 완료!"
echo "❓ 문제가 있다면 ENVIRONMENT_SETUP.md 문서를 참조하세요."
