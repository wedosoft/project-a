#!/bin/bash
"""
EC2 자동 배포 스크립트

하이브리드 임베딩 시스템을 EC2에 최적화하여 배포
"""

set -e

echo "🚀 EC2 하이브리드 임베딩 시스템 배포 시작"

# 시스템 정보 확인
echo "📊 시스템 정보:"
echo "  OS: $(uname -s)"
echo "  Architecture: $(uname -m)" 
echo "  CPU cores: $(nproc)"
echo "  Memory: $(free -h | awk '/^Mem:/ {print $2}')"

# GPU 확인 (선택사항)
if command -v nvidia-smi &> /dev/null; then
    echo "  GPU: $(nvidia-smi --query-gpu=name --format=csv,noheader,nounits)"
else
    echo "  GPU: None (CPU 모드로 실행)"
fi

# Python 환경 설정
echo "🐍 Python 환경 설정"
python3 -m venv venv
source venv/bin/activate

# 의존성 설치
echo "📦 의존성 설치"
pip install --upgrade pip

# PyTorch (CPU 버전)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# sentence-transformers
pip install sentence-transformers

# 기타 의존성
pip install -r requirements.txt

# 환경변수 확인
echo "⚙️ 환경변수 확인"
if [ ! -f .env ]; then
    echo "❌ .env 파일이 없습니다!"
    exit 1
fi

# 임베딩 시스템 테스트
echo "🧪 임베딩 시스템 테스트"
python3 -c "
import sys
sys.path.append('.')

from core.search.embeddings import embed_documents, log_embedding_status

print('=== EC2 임베딩 환경 테스트 ===')
log_embedding_status()

# 간단한 테스트
test_texts = ['EC2 deployment test', 'Embedding system check']
embeddings = embed_documents(test_texts)

if embeddings:
    print(f'✅ 임베딩 성공: {len(embeddings)}개 벡터 생성')
    print(f'벡터 차원: {len(embeddings[0])}')
else:
    print('❌ 임베딩 실패')
    sys.exit(1)
"

# 서비스 시작
echo "🌐 서비스 시작"
python3 -m uvicorn api.main:app --host 0.0.0.0 --port 8000 &

echo "✅ EC2 배포 완료!"
echo "서비스 URL: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):8000"
