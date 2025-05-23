#!/bin/bash
# 500만건 이상 대용량 수집을 위한 스크립트

# 현재 디렉토리를 스크립트 위치로 변경
cd "$(dirname "$0")"

# 환경 설정
export PYTHONPATH="$PYTHONPATH:$(pwd)"

# 필수 패키지 설치 여부 확인
echo "필수 패키지 설치 여부 확인 중..."
pip install -q -r requirements.txt

# 디스크 공간 확인
AVAILABLE_SPACE=$(df -h . | awk 'NR==2 {print $4}')
echo "가용 디스크 공간: $AVAILABLE_SPACE"

# 메모리 확인
MEM_TOTAL=$(free -h | grep Mem | awk '{print $2}')
MEM_AVAIL=$(free -h | grep Mem | awk '{print $7}')
echo "총 메모리: $MEM_TOTAL, 가용 메모리: $MEM_AVAIL"

# 백그라운드에서 수집 실행
echo "대용량 티켓 수집을 백그라운드에서 시작합니다..."
nohup python run_collection.py > freshdesk_full_collection.log 2>&1 &

# PID 저장
echo $! > freshdesk_collection.pid
echo "수집 프로세스 PID: $(cat freshdesk_collection.pid)"

echo "수집이 백그라운드에서 시작되었습니다."
echo "로그 확인: tail -f freshdesk_full_collection.log"
echo "중지하려면: kill $(cat freshdesk_collection.pid)"
echo "실시간 진행 상황 모니터링: ./monitor_collection.sh"
