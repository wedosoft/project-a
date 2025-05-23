"""
대용량 티켓 수집 설정 조정 가이드

500만건 이상의 티켓을 제한 없이 처리하기 위한 최적화 설정
"""

# 1. 메모리 사용량 최적화
CHUNK_SIZE = 5000  # 기존 10,000에서 5,000으로 줄여서 메모리 사용량 감소

# 2. 네트워크 안정성 강화
REQUEST_DELAY = 0.5  # 더 보수적인 요청 간격
MAX_RETRIES = 10     # 재시도 횟수 증가

# 3. 디스크 I/O 최적화
SAVE_INTERVAL = 500  # 더 자주 저장하여 데이터 손실 위험 감소

# 4. 진행 상황 추적 강화
PROGRESS_SAVE_FREQUENCY = 100  # 100개 처리할 때마다 진행 상황 저장

# 5. 시스템 리소스 모니터링
import logging
logger = logging.getLogger(__name__)

def check_system_resources():
    """시스템 리소스 체크 (메모리, 디스크 공간)"""
    import psutil
    
    # 메모리 사용량 체크 (80% 초과시 경고)
    memory = psutil.virtual_memory()
    if memory.percent > 80:
        logger.warning(f"메모리 사용량 높음: {memory.percent}%")
    
    # 디스크 공간 체크 (90% 초과시 경고)  
    disk = psutil.disk_usage('.')
    if disk.percent > 90:
        logger.error(f"디스크 공간 부족: {disk.percent}% 사용 중")
        return False
    
    return True

# 6. 백그라운드 실행 스크립트
BACKGROUND_COLLECTION_SCRIPT = """
#!/bin/bash
# 500만건 수집을 위한 백그라운드 실행 스크립트

# 가상환경 활성화
source venv/bin/activate

# nohup으로 백그라운드 실행
nohup python run_collection.py > collection_5m.log 2>&1 &

# PID 저장
echo $! > collection.pid

echo "대용량 수집이 백그라운드에서 시작되었습니다."
echo "진행 상황: tail -f collection_5m.log"
echo "중단: kill $(cat collection.pid)"
"""

# 7. 모니터링 스크립트
MONITORING_SCRIPT = """
#!/bin/bash
# 수집 진행 상황 모니터링

while true; do
    echo "=== $(date) ==="
    
    # 진행 상황 확인
    if [ -f "freshdesk_100k_data/progress.json" ]; then
        echo "진행 상황:"
        cat freshdesk_100k_data/progress.json | jq '.total_collected, .last_updated'
    fi
    
    # 시스템 리소스 확인
    echo "메모리 사용량: $(free -h | grep Mem | awk '{print $3"/"$2}')"
    echo "디스크 사용량: $(df -h . | tail -1 | awk '{print $3"/"$2" ("$5")"}')"
    
    # 로그 마지막 라인
    echo "최근 로그:"
    tail -n 5 collection_5m.log
    
    echo "------------------------"
    sleep 300  # 5분마다 체크
done
"""

if __name__ == "__main__":
    print("500만건 처리를 위한 설정 가이드:")
    print("1. CHUNK_SIZE를 5000으로 조정")
    print("2. 충분한 디스크 공간 확보 (최소 100GB)")
    print("3. 안정적인 네트워크 환경 필요")
    print("4. 백그라운드 실행 권장")
    print("5. 정기적인 진행 상황 모니터링")
