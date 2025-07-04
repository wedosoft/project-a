#!/bin/bash
# Freshdesk 티켓 수집 도구 실행 스크립트
# 이 스크립트는 새로운 폴더 구조에서 Freshdesk 수집 기능을 실행하는 도우미 스크립트입니다.

echo "Freshdesk 티켓 수집 도구"
echo "========================"
echo "1. 전체 수집 (무제한) 실행"
echo "2. 수집 모니터링"
echo "3. 수집 가이드 문서 열기"
echo "4. 종료"

read -p "선택하세요 (1-4): " choice

case $choice in
  1)
    echo "무제한 티켓 수집을 시작합니다..."
    ./run_full_collection.sh
    ;;
  2)
    echo "수집 모니터링을 시작합니다..."
    ./monitor_collection.sh -w
    ;;
  3)
    echo "수집 가이드 문서를 엽니다..."
    # macOS에서는 open 명령어로 파일 열기
    open ../../docs/FRESHDESK_COLLECTION_GUIDE_INTEGRATED.md
    ;;
  4)
    echo "종료합니다."
    exit 0
    ;;
  *)
    echo "잘못된 선택입니다. 1-4 사이의 번호를 입력하세요."
    exit 1
    ;;
esac
