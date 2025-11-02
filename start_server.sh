#!/bin/bash
# FastAPI 백엔드 실행 스크립트 (루트에서)

echo "🚀 FastAPI 백엔드 시작 중..."
echo ""

# 가상환경 활성화
source venv/bin/activate

# uvicorn 실행
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload