#!/bin/bash
# 티켓 수집 모니터링 스크립트

# 스크립트 디렉토리 경로
SCRIPT_DIR="$(dirname "$0")"
# 백엔드 루트 디렉토리 (상위 폴더의 상위 폴더)
BACKEND_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# 백엔드 디렉토리로 이동
cd "$BACKEND_DIR"

# 결과 디렉토리
OUTPUT_DIR="freshdesk_full_data"

# 진행 상황 확인 함수
check_progress() {
    echo "===== $(date) ====="
    
    # 프로세스 확인
    if [ -f "freshdesk_collection.pid" ]; then
        PID=$(cat freshdesk_collection.pid)
        if ps -p $PID > /dev/null; then
            echo "수집 프로세스 실행 중 (PID: $PID)"
        else
            echo "수집 프로세스가 종료되었습니다!"
        fi
    else
        echo "PID 파일을 찾을 수 없습니다. 프로세스가 실행 중이 아닙니다."
    fi
    
    # 진행 상황 파일 확인
    if [ -f "$OUTPUT_DIR/progress.json" ]; then
        echo "진행 상황:"
        if command -v jq &> /dev/null; then
            cat "$OUTPUT_DIR/progress.json" | jq '.total_collected, .last_updated'
        else
            cat "$OUTPUT_DIR/progress.json" | grep -E 'total_collected|last_updated'
        fi
    else
        echo "진행 상황 파일을 찾을 수 없습니다."
    fi
    
    # 청크 파일 확인
    CHUNK_COUNT=$(ls -1 "$OUTPUT_DIR"/tickets_chunk_*.json 2>/dev/null | wc -l)
    if [ $CHUNK_COUNT -gt 0 ]; then
        echo "저장된 청크 수: $CHUNK_COUNT"
        LAST_CHUNK=$(ls -1t "$OUTPUT_DIR"/tickets_chunk_*.json | head -1)
        echo "마지막 청크: $(basename $LAST_CHUNK)"
        TOTAL_SIZE=$(du -sh "$OUTPUT_DIR" | awk '{print $1}')
        echo "총 데이터 크기: $TOTAL_SIZE"
    else
        echo "아직 저장된 청크가 없습니다."
    fi
    
    # 시스템 리소스 확인
    echo "시스템 리소스:"
    echo "- 메모리 사용량: $(free -h | grep Mem | awk '{print $3"/"$2" ("$3/$2*100"%)"}')"
    echo "- 디스크 사용량: $(df -h . | tail -1 | awk '{print $3"/"$2" ("$5")"}')"
    
    # 최근 로그 확인
    echo "최근 로그 (마지막 5줄):"
    tail -n 5 freshdesk_full_collection.log
    
    echo "------------------------------"
}

# 단일 실행 또는 지속 모니터링
if [ "$1" = "-w" ]; then
    echo "모니터링 시작 (5분 간격으로 업데이트, Ctrl+C로 종료)"
    while true; do
        clear
        check_progress
        sleep 300  # 5분 간격
    done
else
    check_progress
    echo "계속 모니터링하려면: $0 -w"
fi
