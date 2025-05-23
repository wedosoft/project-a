#!/bin/zsh

# 환경 점검 스크립트 (macOS + zsh)
echo "=== [1] Python 버전 확인 ==="
python --version

# backend 폴더 내에서 실행 전제
echo "\n=== [2] 가상환경 활성화 및 패키지 일치 확인 ==="
if [ -d ".venv" ]; then
  source .venv/bin/activate
  pip freeze > /tmp/current.txt
  diff /tmp/current.txt requirements.txt || echo "패키지 차이 있음!"
else
  echo ".venv 폴더가 없습니다."
fi

echo "\n=== [3] .env 파일 존재 및 주요 키 확인 ==="
if [ -f .env ]; then
  grep OPENAI_API_KEY .env || echo "OPENAI_API_KEY 없음"
else
  echo ".env 파일 없음!"
fi

echo "\n=== [4] PYTHONPATH, PATH 확인 ==="
echo "PYTHONPATH: $PYTHONPATH"
echo "PATH: $PATH"

echo "\n=== [5] attachment_cache 폴더 및 파일 개수 ==="
if [ -d attachment_cache ]; then
  echo "파일 개수: $(ls -1 attachment_cache | wc -l)"
else
  echo "attachment_cache 폴더 없음"
fi

echo "\n=== [6] OpenAI API 네트워크 접근성 테스트 ==="
if grep -q OPENAI_API_KEY .env; then
  export $(grep OPENAI_API_KEY .env | xargs)
  curl -s https://api.openai.com/v1/models -H "Authorization: Bearer $OPENAI_API_KEY" | head -c 200
else
  echo "OPENAI_API_KEY 환경변수 없음"
fi

echo "\n=== 환경 점검 완료 ==="
