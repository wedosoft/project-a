#!/bin/bash

# Freshdesk AI Assistant Backend 시작 스크립트
# 이 스크립트는 Python path를 올바르게 설정하고 uvicorn 서버를 시작합니다.

# 현재 디렉토리 (backend)를 확인
BACKEND_DIR=$(pwd)
echo "Backend 디렉토리: $BACKEND_DIR"

# Python path에 backend 디렉토리 추가
export PYTHONPATH="$BACKEND_DIR:$PYTHONPATH"
echo "PYTHONPATH 설정: $PYTHONPATH"

# 가상환경 활성화
if [ -f "venv/bin/activate" ]; then
    echo "가상환경 활성화 중..."
    source venv/bin/activate
else
    echo "⚠️  가상환경을 찾을 수 없습니다. venv/bin/activate가 존재하는지 확인해주세요."
    exit 1
fi

# 환경변수 확인
if [ ! -f ".env" ]; then
    echo "⚠️  .env 파일을 찾을 수 없습니다."
    exit 1
fi

echo "🚀 FastAPI 서버 시작 중..."
echo "   - 호스트: 0.0.0.0"
echo "   - 포트: 8000"
echo "   - 리로드: 활성화"
echo ""

# uvicorn 실행
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
