#!/bin/bash
# 가상환경 활성화 스크립트

cd "$(dirname "$0")"
source venv/bin/activate

echo "🐍 Python 가상환경이 활성화되었습니다."
echo "🚀 이제 'python main.py'로 서버를 실행할 수 있습니다."
echo "📝 가상환경을 종료하려면 'deactivate' 명령어를 사용하세요."